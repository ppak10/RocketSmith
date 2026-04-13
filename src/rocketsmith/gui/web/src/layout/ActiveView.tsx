import { useEffect, useRef, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { fetchText } from "@/lib/server";
import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
} from "@dnd-kit/core";
import type { DragEndEvent, DragStartEvent, DragOverEvent } from "@dnd-kit/core";
import { DraggableCard } from "@/components/DraggableCard";
import { SessionLogCard, eventsToLogs } from "@/components/SessionLogCard";
import { ProgressCard, useProgressData } from "@/components/ProgressCard";
import { ComponentTreeCard } from "@/components/ComponentTreeCard";
import type { LogEntry } from "@/components/SessionLogCard";
import { usePreferences } from "@/hooks/usePreferences";
import type { CardLayout } from "@/hooks/usePreferences";
import { getCardDef, GRID_COL_MIN, GRID_ROW_H, GRID_GAP } from "./cardRegistry";
import { PartCard } from "@/components/PartCard";
import type { WatchEvent } from "@/hooks/useWatchSocket";
import { useRotatingAscii } from "@/hooks/useRotatingAscii";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";

interface ActiveViewProps {
  events: WatchEvent[];
  offline: boolean;
  treeVersion: number;
}

/** Format directory prefixes we track for grouped badges. */
const FORMAT_DIRS = new Set(["cadsmith/source", "cadsmith/step", "cadsmith/stl", "prusaslicer/gcode"]);

function getStem(path: string): string {
  const name = path.split("/").pop() ?? path;
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(0, dot) : name;
}

/**
 * Check if an event is a part file (lives under a known format dir).
 * Returns the matching format directory prefix or null.
 */
function getPartFormat(event: WatchEvent): string | null {
  const rel = event.relative_path;
  for (const prefix of FORMAT_DIRS) {
    if (rel.startsWith(prefix + "/")) return prefix;
  }
  return null;
}

/** Group part events by stem name, tracking which formats are complete. */
interface PartGroup {
  stem: string;
  formats: Set<string>;
  latestEvent: WatchEvent;
  latestTimestamp: string;
}

function groupPartEvents(events: WatchEvent[]): PartGroup[] {
  const map = new Map<string, PartGroup>();

  for (const e of events) {
    const fmt = getPartFormat(e);
    if (!fmt) continue;
    const stem = getStem(e.path);

    const existing = map.get(stem);
    if (existing) {
      existing.formats.add(fmt);
      if (e.timestamp > existing.latestTimestamp) {
        existing.latestEvent = e;
        existing.latestTimestamp = e.timestamp;
      }
    } else {
      map.set(stem, {
        stem,
        formats: new Set([fmt]),
        latestEvent: e,
        latestTimestamp: e.timestamp,
      });
    }
  }

  // Sort by latest timestamp descending.
  return Array.from(map.values()).sort(
    (a, b) => b.latestTimestamp.localeCompare(a.latestTimestamp),
  );
}

// ── Grid with background lines ──────────────────────────────────────────────

/** A single droppable grid cell. Highlight state controlled by parent. */
function DroppableCell({
  id,
  highlighted = false,
}: {
  id: string;
  highlighted?: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <div
      ref={setNodeRef}
      className={`rounded-base border border-dashed transition-colors ${
        isOver || highlighted
          ? "border-main/60 bg-main/5"
          : "border-border/20 dark:border-border/80"
      }`}
    />
  );
}

/** Clamp a stored layout to fit within the current grid dimensions. */
function reflowLayout(
  layout: CardLayout,
  def: ReturnType<typeof getCardDef>,
  cols: number,
): CardLayout {
  let { col, row, colSpan, rowSpan } = layout;
  // Clamp span to available columns.
  if (colSpan > cols) colSpan = cols;
  // Clamp position so card fits.
  if (col + colSpan - 1 > cols) col = Math.max(1, cols - colSpan + 1);
  if (row < 1) row = 1;
  return { col, row, colSpan, rowSpan };
}

function AgentFeedGrid({
  cardIds,
  visibleCards,
  layouts,
  sensors,
  onDragEnd,
  onResizeEnd,
  activeCardId,
}: {
  cardIds: string[];
  visibleCards: Record<string, ReactNode>;
  layouts: Record<string, CardLayout>;
  sensors: ReturnType<typeof useSensors>;
  onDragEnd: (event: DragEndEvent) => void;
  onResizeEnd: (cardId: string, colSpan: number, rowSpan: number) => void;
  activeCardId: string | null;
}) {
  const gridRef = useRef<HTMLDivElement>(null);
  const [cols, setCols] = useState(3);
  const [rows, setRows] = useState(4);

  useEffect(() => {
    const el = gridRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width;
      const h = entry.contentRect.height;
      const c = Math.max(1, Math.floor((w + GRID_GAP) / (GRID_COL_MIN + GRID_GAP)));
      const r = Math.max(1, Math.ceil((h + GRID_GAP) / (GRID_ROW_H + GRID_GAP)));
      setCols(c);
      setRows(r);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Compute reflowed layouts (render-only, not persisted).
  const reflowed = useMemo(() => {
    const result: Record<string, CardLayout> = {};
    for (const id of cardIds) {
      const stored = layouts[id];
      const def = getCardDef(id);
      if (stored) {
        result[id] = reflowLayout(stored, def, cols);
      }
    }
    return result;
  }, [cardIds, layouts, cols]);

  // Enough rows to fill viewport or fit all placed cards.
  let maxRow = rows;
  for (const id of cardIds) {
    const layout = reflowed[id];
    const def = getCardDef(id);
    const rSpan = layout?.rowSpan ?? def?.rowSpan ?? 1;
    const r = layout?.row ?? 1;
    maxRow = Math.max(maxRow, r + rSpan - 1);
  }
  const displayRows = maxRow;

  // Track active drag and hover for multi-cell highlighting.
  const [activeId, setActiveId] = useState<string | null>(null);
  const [overCellId, setOverCellId] = useState<string | null>(null);

  const activeDef = activeId ? getCardDef(activeId) : null;
  const activeLayout = activeId ? reflowed[activeId] : null;
  const activeCols = activeLayout?.colSpan ?? activeDef?.colSpan ?? 1;
  const activeRows = activeLayout?.rowSpan ?? activeDef?.rowSpan ?? 1;

  // Compute which cells should be highlighted based on hover + card span.
  const highlightedCells = useMemo(() => {
    const set = new Set<string>();
    if (!overCellId || !activeId) return set;
    const match = overCellId.match(/^cell-(\d+)-(\d+)$/);
    if (!match) return set;
    const hoverCol = parseInt(match[1], 10);
    const hoverRow = parseInt(match[2], 10);
    for (let dc = 0; dc < activeCols; dc++) {
      for (let dr = 0; dr < activeRows; dr++) {
        const c = hoverCol + dc;
        const r = hoverRow + dr;
        if (c <= cols && r <= displayRows) {
          set.add(`cell-${c}-${r}`);
        }
      }
    }
    return set;
  }, [overCellId, activeId, activeCols, activeRows, cols, displayRows]);

  function handleDragStart(event: DragStartEvent) {
    setActiveId(event.active.id as string);
  }

  function handleDragOver(event: DragOverEvent) {
    const overId = event.over?.id as string | undefined;
    setOverCellId(overId?.startsWith("cell-") ? overId : null);
  }

  function handleDragEndInternal(event: DragEndEvent) {
    setActiveId(null);
    setOverCellId(null);
    onDragEnd(event);
  }

  return (
    <div ref={gridRef} className="relative flex-1 overflow-hidden">
      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEndInternal}
      >
        {/* Background droppable cells — always 1×1 */}
        <div
          className="absolute inset-0 grid"
          style={{
            gridTemplateColumns: `repeat(${cols}, 1fr)`,
            gridAutoRows: `${GRID_ROW_H}px`,
            gap: `${GRID_GAP}px`,
          }}
        >
          {Array.from({ length: cols * displayRows }).map((_, i) => {
            const c = (i % cols) + 1;
            const r = Math.floor(i / cols) + 1;
            const cellId = `cell-${c}-${r}`;
            return (
              <DroppableCell
                key={cellId}
                id={cellId}
                highlighted={highlightedCells.has(cellId)}
              />
            );
          })}
        </div>

        {/* Cards grid — overlays the droppable cells */}
        <div
          className="relative grid h-full"
          style={{
            gridTemplateColumns: `repeat(${cols}, 1fr)`,
            gridAutoRows: `${GRID_ROW_H}px`,
            gap: `${GRID_GAP}px`,
          }}
        >
          {cardIds.map((id) => {
            const def = getCardDef(id);
            const layout = reflowed[id];
            const cs = layout?.colSpan ?? def?.colSpan ?? 1;
            const rs = layout?.rowSpan ?? def?.rowSpan ?? 1;
            return (
              <DraggableCard
                key={id}
                id={id}
                colSpan={cs}
                rowSpan={rs}
                col={layout?.col}
                row={layout?.row}
                gridCols={cols}
                minColSpan={def?.minColSpan ?? 1}
                maxColSpan={def?.maxColSpan ?? 2}
                minRowSpan={def?.minRowSpan ?? 1}
                maxRowSpan={def?.maxRowSpan ?? 3}
                onResizeEnd={(newCs, newRs) => onResizeEnd(id, newCs, newRs)}
                active={id === activeCardId}
              >
                {visibleCards[id]}
              </DraggableCard>
            );
          })}
        </div>
      </DndContext>
    </div>
  );
}

// ── Main view ───────────────────────────────────────────────────────────────

export function ActiveView({ events, offline, treeVersion }: ActiveViewProps) {
  const asciiFrame = useRotatingAscii();
  const progressData = useProgressData(treeVersion);

  // Historical logs from file + live logs from events.
  const [historicalLogs, setHistoricalLogs] = useState<LogEntry[]>([]);
  useEffect(() => {
    fetchText("gui/logs/session.jsonl")
      .then((text) => {
        if (!text) return;
        const entries = text
          .trim()
          .split("\n")
          .map((line) => {
            try { return JSON.parse(line) as LogEntry; }
            catch { return null; }
          })
          .filter(Boolean) as LogEntry[];
        setHistoricalLogs(entries);
      })
      .catch(() => {});
  }, []);

  const liveLogs = useMemo(() => eventsToLogs(events), [events]);
  const sessionLogs = useMemo(
    () => [...historicalLogs, ...liveLogs],
    [historicalLogs, liveLogs],
  );

  // Preferences (must be called before any early return).
  const { agentFeedLayout, setAgentFeedLayout } = usePreferences();

  // Drag-and-drop setup.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );

  // Separate part events from non-part events.
  const { partGroups, nonPartEvents } = useMemo(() => {
    const partEvts: WatchEvent[] = [];
    const nonPart: WatchEvent[] = [];

    for (const e of events) {
      if (getPartFormat(e) !== null) {
        partEvts.push(e);
      } else {
        nonPart.push(e);
      }
    }

    return {
      partGroups: groupPartEvents(partEvts),
      nonPartEvents: nonPart,
    };
  }, [events]);

  // Filter to renderable event types: parts, assembly, manifest.
  const RENDERABLE_TYPES = new Set(["manifest", "assembly"]);
  const renderableNonPart = [...nonPartEvents]
    .reverse()
    .find((e) => RENDERABLE_TYPES.has(e.type)) ?? null;

  // Build visible cards keyed by card ID.
  const visibleCards: Record<string, ReactNode> = {};

  // One PartCard per part that has been worked on.
  // Find the latest source event per part for diff highlighting.
  const sourceEvents = new Map<string, WatchEvent>();
  for (const e of events) {
    if (e.relative_path.startsWith("cadsmith/source/") && e.relative_path.endsWith(".py")) {
      const stem = e.relative_path.replace("cadsmith/source/", "").replace(".py", "");
      sourceEvents.set(stem, e);
    }
  }

  for (const group of partGroups) {
    const hasStl = group.formats.has("cadsmith/stl");
    const srcEvent = sourceEvents.get(group.stem);
    visibleCards[`part-${group.stem}`] = (
      <PartCard
        partName={group.stem}
        autoRotate
        simpleControls
        showModeToggle={false}
        defaultTab={hasStl ? "model" : "source"}
        previousSourceContent={srcEvent?.previous_content ?? null}
        className="h-full"
      />
    );
  }

  if (renderableNonPart) {
    visibleCards["assembly"] = <ComponentTreeCard className="h-full" />;
  }

  if (progressData.length > 0) {
    visibleCards["build-progress"] = <ProgressCard parts={progressData} />;
  }

  if (sessionLogs.length > 0) {
    visibleCards["session-log"] = <SessionLogCard logs={sessionLogs} />;
  }

  const cardIds = Object.keys(visibleCards);

  // Determine which card is "active" (most recently updated by an event).
  const activeCardId = useMemo(() => {
    if (events.length === 0) return null;
    const latest = events[events.length - 1];
    const fmt = getPartFormat(latest);
    if (fmt) return `part-${getStem(latest.path)}`;
    if (latest.type === "manifest" || latest.type === "assembly") return "assembly";
    if (latest.type === "preview") return "build-progress";
    if (latest.type === "log") return "session-log";
    return null;
  }, [events]);

  // Show waiting placeholder only when online with no activity yet.
  if (!offline && events.length === 0 && sessionLogs.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="relative inline-flex items-center justify-center">
          <pre className="select-none text-[3px] leading-[3px] font-semibold text-foreground/20 sm:text-[4px] sm:leading-[4px] xl:text-[6px] xl:leading-[6px]">
            {asciiFrame}
          </pre>
          <div className="absolute inset-0 flex items-start justify-center">
            <Alert className="w-auto">
              <AlertTitle>Waiting for activity...</AlertTitle>
              <AlertDescription>
                The agent hasn&apos;t started yet
              </AlertDescription>
            </Alert>
          </div>
        </div>
      </div>
    );
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;
    const overId = over.id as string;
    const match = overId.match(/^cell-(\d+)-(\d+)$/);
    if (!match) return;
    const col = parseInt(match[1], 10);
    const row = parseInt(match[2], 10);
    const cardId = active.id as string;
    // Preserve existing span values when moving.
    const existing = agentFeedLayout[cardId];
    const def = getCardDef(cardId);
    setAgentFeedLayout({
      ...agentFeedLayout,
      [cardId]: {
        col,
        row,
        colSpan: existing?.colSpan ?? def?.colSpan ?? 1,
        rowSpan: existing?.rowSpan ?? def?.rowSpan ?? 1,
      },
    });
  }

  function handleResizeEnd(cardId: string, colSpan: number, rowSpan: number) {
    const existing = agentFeedLayout[cardId];
    const def = getCardDef(cardId);
    setAgentFeedLayout({
      ...agentFeedLayout,
      [cardId]: {
        col: existing?.col ?? 1,
        row: existing?.row ?? 1,
        colSpan,
        rowSpan,
      },
    });
  }

  return (
    <div className="flex h-full flex-col p-4">
      {offline && (
        <Alert className="mb-4 w-full">
          <AlertTitle>Offline mode</AlertTitle>
          <AlertDescription>
            Showing previously generated data. Start the GUI server for live
            updates.
          </AlertDescription>
        </Alert>
      )}

      <AgentFeedGrid
        cardIds={cardIds}
        visibleCards={visibleCards}
        layouts={agentFeedLayout}
        sensors={sensors}
        onDragEnd={handleDragEnd}
        onResizeEnd={handleResizeEnd}
        activeCardId={activeCardId}
      />
    </div>
  );
}

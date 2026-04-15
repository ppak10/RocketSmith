import { useEffect, useRef, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { fetchText, hasOfflineFile } from "@/lib/server";
import {
  DndContext,
  PointerSensor,
  pointerWithin,
  useSensor,
  useSensors,
  useDroppable,
} from "@dnd-kit/core";
import type { DragEndEvent, DragStartEvent, DragOverEvent } from "@dnd-kit/core";
import { DraggableCard } from "@/components/DraggableCard";
import { SessionLogCard, eventsToLogs } from "@/components/SessionLogCard";
import { useProgressData } from "@/components/ProgressCard";
import { ComponentTreeCard } from "@/components/ComponentTreeCard";
import { FlightCard } from "@/components/FlightCard";
import type { LogEntry } from "@/components/SessionLogCard";
import { usePreferences } from "@/hooks/usePreferences";
import type { CardLayout } from "@/hooks/usePreferences";
import { getCardDef, GRID_COL_MIN, GRID_ROW_H, GRID_GAP } from "./cardRegistry";
import { PartCard } from "@/components/PartCard";
import type { WatchEvent } from "@/hooks/useWatchSocket";
import { useRotatingAscii } from "@/hooks/useRotatingAscii";
import { LayoutGrid, Focus } from "lucide-react";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";

interface ActiveViewProps {
  events: WatchEvent[];
  offline: boolean;
  treeVersion: number;
}

/** Format directory prefixes we track for grouped badges. */
const FORMAT_DIRS = new Set(["cadsmith/source", "cadsmith/step", "gui/assets/stl", "prusaslicer/gcode"]);

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
  /** Latest timestamp per format directory prefix. */
  formatTimestamps: Map<string, string>;
  latestEvent: WatchEvent;
  latestTimestamp: string;
}

/**
 * Pipeline stage order. A downstream stage is only considered "done" if
 * its latest event is newer than the latest event of any upstream stage.
 * This handles regeneration: when source is re-written, step/stl/gcode
 * reset to pending until they catch up.
 */
const PIPELINE_ORDER = ["cadsmith/source", "cadsmith/step", "gui/assets/stl", "prusaslicer/gcode"];

/** Given per-format timestamps, return the set of formats that are current (not stale). */
function currentFormats(formatTimestamps: Map<string, string>): Set<string> {
  const result = new Set<string>();
  let latestUpstream = "";

  for (const key of PIPELINE_ORDER) {
    const ts = formatTimestamps.get(key);
    if (ts && ts >= latestUpstream) {
      result.add(key);
      latestUpstream = ts;
    } else {
      // This stage and all downstream are stale — stop here.
      break;
    }
  }
  return result;
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
      const prev = existing.formatTimestamps.get(fmt);
      if (!prev || e.timestamp > prev) {
        existing.formatTimestamps.set(fmt, e.timestamp);
      }
      if (e.timestamp > existing.latestTimestamp) {
        existing.latestEvent = e;
        existing.latestTimestamp = e.timestamp;
      }
    } else {
      map.set(stem, {
        stem,
        formats: new Set([fmt]),
        formatTimestamps: new Map([[fmt, e.timestamp]]),
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

// ── Grid ────────────────────────────────────────────────────────────────────

const CELL_W = GRID_COL_MIN + GRID_GAP;
const CELL_H = GRID_ROW_H + GRID_GAP;
const MIN_DISPLAY = 4;  // Minimum background cells to show.
const MIN_PACK = 2;     // Minimum columns for auto-placement packing.

/** A single droppable grid cell. Highlight state controlled by parent. */
function DroppableCell({
  id,
  col,
  row,
  highlighted = false,
}: {
  id: string;
  col: number;
  row: number;
  highlighted?: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <div
      ref={setNodeRef}
      style={{ gridColumn: col, gridRow: row }}
      className={`rounded-base border border-dashed transition-colors ${
        isOver || highlighted
          ? "border-main/60 bg-main/5"
          : "border-border/20 dark:border-border/80"
      }`}
    />
  );
}

function AgentFeedGrid({
  cardIds,
  visibleCards,
  layouts,
  sensors,
  onDragEnd,
  onResizeEnd,
  onPersistLayouts,
  activeCardId,
  autoFocus,
}: {
  cardIds: string[];
  visibleCards: Record<string, ReactNode>;
  layouts: Record<string, CardLayout>;
  sensors: ReturnType<typeof useSensors>;
  onDragEnd: (event: DragEndEvent) => void;
  onResizeEnd: (cardId: string, colSpan: number, rowSpan: number) => void;
  onPersistLayouts: (layouts: Record<string, CardLayout>) => void;
  activeCardId: string | null;
  autoFocus: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Scroll the active card into view when it changes (if auto-focus is on).
  useEffect(() => {
    if (!autoFocus || !activeCardId || !containerRef.current) return;
    const el = containerRef.current.querySelector(`[data-card-id="${activeCardId}"]`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
    }
  }, [autoFocus, activeCardId]);

  // Viewport cell count — only used for auto-placement bounds and background cells.
  const [viewCols, setViewCols] = useState(() =>
    Math.max(MIN_PACK, Math.floor(window.innerWidth / CELL_W)),
  );
  const [viewRows, setViewRows] = useState(() =>
    Math.max(MIN_PACK, Math.floor(window.innerHeight / CELL_H)),
  );

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width;
      const h = entry.contentRect.height;
      setViewCols(Math.max(MIN_PACK, Math.floor(w / CELL_W)));
      setViewRows(Math.max(MIN_PACK, Math.floor(h / CELL_H)));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Auto-assign positions for cards without stored layouts.
  // Uses a simple occupied-cell grid to find the first open slot.
  const effectiveLayouts = useMemo(() => {
    const result: Record<string, CardLayout> = {};
    const occupied = new Set<string>();

    // Mark cells occupied by cards that already have positions.
    for (const id of cardIds) {
      const layout = layouts[id];
      if (!layout?.col || !layout?.row) continue;
      result[id] = layout;
      const cs = layout.colSpan ?? getCardDef(id)?.colSpan ?? 1;
      const rs = layout.rowSpan ?? getCardDef(id)?.rowSpan ?? 1;
      for (let dc = 0; dc < cs; dc++) {
        for (let dr = 0; dr < rs; dr++) {
          occupied.add(`${layout.col + dc},${layout.row + dr}`);
        }
      }
    }

    // Place unpositioned cards in the first available slot.
    for (const id of cardIds) {
      if (result[id]) continue;
      const def = getCardDef(id);
      const cs = def?.colSpan ?? 1;
      const rs = def?.rowSpan ?? 1;

      let placed = false;
      for (let r = 1; !placed; r++) {
        for (let c = 1; c + cs - 1 <= viewCols; c++) {
          // Check if the card fits here without overlapping.
          let fits = true;
          for (let dc = 0; dc < cs && fits; dc++) {
            for (let dr = 0; dr < rs && fits; dr++) {
              if (occupied.has(`${c + dc},${r + dr}`)) fits = false;
            }
          }
          if (fits) {
            result[id] = { col: c, row: r, colSpan: cs, rowSpan: rs };
            for (let dc = 0; dc < cs; dc++) {
              for (let dr = 0; dr < rs; dr++) {
                occupied.add(`${c + dc},${r + dr}`);
              }
            }
            placed = true;
          }
        }
      }
    }

    // Persist any newly auto-placed cards so they become fixed.
    const newPlacements: Record<string, CardLayout> = {};
    for (const id of cardIds) {
      if (!layouts[id]?.col && result[id]) {
        newPlacements[id] = result[id];
      }
    }
    if (Object.keys(newPlacements).length > 0) {
      // Schedule the persist outside the render cycle.
      queueMicrotask(() => onPersistLayouts({ ...layouts, ...newPlacements }));
    }

    return result;
  }, [cardIds, layouts, viewCols]);

  // Compute grid dimensions: enough to fit all cards OR fill the viewport.
  let contentCols = MIN_DISPLAY;
  let contentRows = MIN_DISPLAY;
  for (const id of cardIds) {
    const layout = effectiveLayouts[id];
    if (!layout) continue;
    contentCols = Math.max(contentCols, layout.col + layout.colSpan - 1);
    contentRows = Math.max(contentRows, layout.row + layout.rowSpan - 1);
  }
  const displayCols = Math.max(viewCols, contentCols + 1, MIN_DISPLAY);
  const displayRows = Math.max(viewRows, contentRows + 1, MIN_DISPLAY);

  // Track active drag and hover for multi-cell highlighting.
  const [dragId, setDragId] = useState<string | null>(null);
  const [overCellId, setOverCellId] = useState<string | null>(null);

  const dragDef = dragId ? getCardDef(dragId) : null;
  const dragLayout = dragId ? effectiveLayouts[dragId] : null;
  const dragCols = dragLayout?.colSpan ?? dragDef?.colSpan ?? 1;
  const dragRows = dragLayout?.rowSpan ?? dragDef?.rowSpan ?? 1;

  const highlightedCells = useMemo(() => {
    const set = new Set<string>();
    if (!overCellId || !dragId) return set;
    const match = overCellId.match(/^cell-(\d+)-(\d+)$/);
    if (!match) return set;
    const hoverCol = parseInt(match[1], 10);
    const hoverRow = parseInt(match[2], 10);
    for (let dc = 0; dc < dragCols; dc++) {
      for (let dr = 0; dr < dragRows; dr++) {
        set.add(`cell-${hoverCol + dc}-${hoverRow + dr}`);
      }
    }
    return set;
  }, [overCellId, dragId, dragCols, dragRows]);

  function handleDragStart(event: DragStartEvent) {
    setDragId(event.active.id as string);
  }

  function handleDragOver(event: DragOverEvent) {
    const overId = event.over?.id as string | undefined;
    setOverCellId(overId?.startsWith("cell-") ? overId : null);
  }

  function handleDragEndInternal(event: DragEndEvent) {
    setDragId(null);
    setOverCellId(null);
    onDragEnd(event);
  }

  const gridStyle = {
    gridTemplateColumns: `repeat(${displayCols}, ${GRID_COL_MIN}px)`,
    gridAutoRows: `${GRID_ROW_H}px`,
    gap: `${GRID_GAP}px`,
  };

  return (
    <div ref={containerRef} data-slot="agent-feed-grid" className="flex-1 overflow-auto">
      <DndContext
        sensors={sensors}
        collisionDetection={pointerWithin}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEndInternal}
      >
        <div className="relative min-h-full min-w-full" style={{ width: "max-content" }}>
          {/* Background droppable cells */}
          <div className="absolute inset-0 grid" style={gridStyle}>
            {Array.from({ length: displayCols * displayRows }).map((_, i) => {
              const c = (i % displayCols) + 1;
              const r = Math.floor(i / displayCols) + 1;
              const cellId = `cell-${c}-${r}`;
              return (
                <DroppableCell
                  key={cellId}
                  id={cellId}
                  col={c}
                  row={r}
                  highlighted={highlightedCells.has(cellId)}
                />
              );
            })}
          </div>

          {/* Cards layer — overlays droppable cells */}
          <div className="relative grid" style={gridStyle}>
            {cardIds.map((id) => {
              const def = getCardDef(id);
              const layout = effectiveLayouts[id];
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
                  gridCols={displayCols}
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
        </div>
      </DndContext>
    </div>
  );
}

// ── Main view ───────────────────────────────────────────────────────────────

export function ActiveView({ events, offline, treeVersion }: ActiveViewProps) {
  const asciiFrame = useRotatingAscii();
  const progressData = useProgressData(treeVersion);

  // Historical logs from file. Re-parsed whenever the watcher broadcasts a
  // "log" event for session.jsonl (uses the event's inline content so no extra
  // fetch is needed).
  const [historicalLogs, setHistoricalLogs] = useState<LogEntry[]>([]);

  function parseSessionJsonl(text: string): LogEntry[] {
    return text
      .trim()
      .split("\n")
      .map((line) => {
        try { return JSON.parse(line) as LogEntry; }
        catch { return null; }
      })
      .filter(Boolean) as LogEntry[];
  }

  useEffect(() => {
    fetchText("gui/logs/session.jsonl")
      .then((text) => { if (text) setHistoricalLogs(parseSessionJsonl(text)); })
      .catch(() => {});
  }, []);

  // Re-parse historicalLogs whenever a fresh session.jsonl is broadcast.
  useEffect(() => {
    const latest = [...events].reverse().find(
      (e) => e.type === "log" && e.relative_path === "gui/logs/session.jsonl" && e.content,
    );
    if (latest?.content) setHistoricalLogs(parseSessionJsonl(latest.content));
  }, [events]);

  // Exclude "log" events from liveLogs — they are handled above via historicalLogs.
  const liveLogs = useMemo(() => eventsToLogs(events.filter((e) => e.type !== "log")), [events]);
  const sessionLogs = useMemo(
    () => [...historicalLogs, ...liveLogs],
    [historicalLogs, liveLogs],
  );

  // Preferences (must be called before any early return).
  const { agentFeedLayout, setAgentFeedLayout } = usePreferences();

  // Drag-and-drop setup.
  const [autoFocus, setAutoFocus] = useState(true);

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

  // Show the component tree card if a live manifest/assembly event arrived
  // OR the component_tree.json already exists in the offline bundle (e.g.
  // generated before the browser connected).
  const RENDERABLE_TYPES = new Set(["manifest", "assembly", "openrocket"]);
  const renderableNonPart = [...nonPartEvents]
    .reverse()
    .find((e) => RENDERABLE_TYPES.has(e.type)) ?? null;
  const hasExistingTree = useMemo(
    () => hasOfflineFile("gui/component_tree.json"),
    // Re-check whenever the offline bundle's file tree is updated.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [treeVersion],
  );

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

  // Build a per-part progress lookup.
  const progressByPart = useMemo(() => {
    const map = new Map<string, Record<string, { status: string; path: string | null }>>();
    for (const p of progressData) {
      map.set(p.part_name, p.outputs);
    }
    return map;
  }, [progressData]);

  // Count STL events per part to trigger 3D viewer refresh.
  const stlVersionByPart = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of events) {
      if (e.relative_path.startsWith("gui/assets/stl/") && e.relative_path.endsWith(".stl")) {
        const stem = getStem(e.path);
        map.set(stem, (map.get(stem) ?? 0) + 1);
      }
    }
    return map;
  }, [events]);

  for (const group of partGroups) {
    const current = currentFormats(group.formatTimestamps);
    const hasStl = current.has("gui/assets/stl");
    const srcEvent = sourceEvents.get(group.stem);
    visibleCards[`part-${group.stem}`] = (
      <PartCard
        partName={group.stem}
        autoRotate
        simpleControls
        staticPreview
        showModeToggle={false}
        defaultTab={hasStl ? "model" : "source"}
        previousSourceContent={srcEvent?.previous_content ?? null}
        progress={progressByPart.get(group.stem) ?? null}
        stlVersion={stlVersionByPart.get(group.stem) ?? 0}
        completedFormats={current}
        className="h-full"
      />
    );
  }

  // Count manifest events so the card re-fetches on each update.
  const manifestVersion = useMemo(
    () => events.filter((e) => e.type === "manifest").length + treeVersion,
    [events, treeVersion],
  );

  if (renderableNonPart || hasExistingTree) {
    visibleCards["assembly"] = <ComponentTreeCard className="h-full" treeVersion={manifestVersion} />;
  }

  // Show flight card when a flight event arrives or flight data already exists.
  const hasFlightEvent = events.some((e) => e.type === "flight");
  const flightVersion = useMemo(
    () => events.filter((e) => e.type === "flight").length + treeVersion,
    [events, treeVersion],
  );
  if (hasFlightEvent) {
    visibleCards["flight"] = <FlightCard className="h-full" treeVersion={flightVersion} />;
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
    if (latest.type === "flight") return "flight";
    if (latest.type === "preview") return "build-progress";
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
    const { active, over, delta } = event;
    const cardId = active.id as string;
    const existing = agentFeedLayout[cardId];
    const def = getCardDef(cardId);

    let col: number;
    let row: number;

    // Try to use the droppable cell the pointer is over.
    const match = (over?.id as string)?.match(/^cell-(\d+)-(\d+)$/);
    if (match) {
      col = parseInt(match[1], 10);
      row = parseInt(match[2], 10);
    } else {
      // Fallback: compute target from drag delta + original position.
      const origCol = existing?.col ?? 1;
      const origRow = existing?.row ?? 1;
      col = Math.max(1, origCol + Math.round(delta.x / CELL_W));
      row = Math.max(1, origRow + Math.round(delta.y / CELL_H));
    }

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
        onPersistLayouts={setAgentFeedLayout}
        activeCardId={activeCardId}
        autoFocus={autoFocus}
      />

      {/* Bottom-right floating controls */}
      <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setAutoFocus((v) => !v)}
          className={`cursor-pointer select-none flex items-center gap-2 rounded-base border-2 border-border px-3 py-2 text-xs font-heading shadow-shadow transition-colors ${
            autoFocus
              ? "bg-main text-main-foreground"
              : "bg-background text-foreground hover:bg-main hover:text-main-foreground"
          }`}
        >
          <Focus className="size-4" />
          Auto-focus
        </button>
        <button
          type="button"
          onClick={() => setAgentFeedLayout({})}
          className="flex items-center gap-2 rounded-base border-2 border-border bg-background px-3 py-2 text-xs font-heading shadow-shadow transition-colors hover:bg-main hover:text-main-foreground"
        >
          <LayoutGrid className="size-4" />
          Reset Layout
        </button>
      </div>
    </div>
  );
}

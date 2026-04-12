import { Suspense, useCallback, useEffect, useRef, useMemo, useState } from "react";
import { fileUrl, fetchJson, fetchText, hasOfflineFile } from "@/lib/server";
import {
  Box,
  LineChart,
  FileText,
  Cog,
  Package,
  Printer,
} from "lucide-react";
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { OrbitControls, Environment, Center } from "@react-three/drei";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import * as THREE from "three";
import type { Group } from "three";
import type { WatchEvent } from "@/hooks/useWatchSocket";
import { useRotatingAscii } from "@/hooks/useRotatingAscii";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import { RocketProfile } from "@/components/RocketProfile";
import { useFileTree } from "@/hooks/useFileTree";
import type { FileNode } from "@/hooks/useFileTree";

interface ActiveViewProps {
  events: WatchEvent[];
  offline: boolean;
  treeVersion: number;
}

const TYPE_META: Record<
  string,
  { icon: typeof Box; label: string; verb: string }
> = {
  cadsmith: { icon: Cog, label: "CADSMITH", verb: "Writing script" },
  step: { icon: Box, label: "STEP", verb: "Generating" },
  stl: { icon: Box, label: "STL", verb: "Exporting" },
  parts: { icon: Box, label: "PART", verb: "Extracting" },
  openrocket: { icon: LineChart, label: "OPENROCKET", verb: "Updating design" },
  flight: { icon: LineChart, label: "FLIGHT", verb: "Running flight" },
  assembly: { icon: Box, label: "ASSEMBLY", verb: "Building assembly" },
  report: { icon: FileText, label: "REPORT", verb: "Reporting" },
  manifest: { icon: Package, label: "MANIFEST", verb: "Building manifest" },
  gcode: { icon: Printer, label: "GCODE", verb: "Slicing" },
  script: { icon: Cog, label: "SCRIPT", verb: "Running script" },
  unknown: { icon: Cog, label: "FILE", verb: "Processing" },
};

/** Format directory prefixes we track for grouped badges. */
const FORMAT_DIRS = new Set(["cadsmith/source", "cadsmith/step", "cadsmith/stl", "prusaslicer/gcode"]);
const PART_FORMATS = ["cadsmith/source", "cadsmith/step", "cadsmith/stl", "gui/assets/png", "gui/assets/gif"] as const;

/** Text extensions for diff preview. */
const TEXT_EXTENSIONS = new Set([
  ".json", ".md", ".py", ".csv", ".txt",
  ".ini", ".cfg", ".toml", ".yaml", ".yml", ".gcode",
]);

function getFilename(path: string): string {
  return path.split("/").pop() ?? path;
}

function getStem(path: string): string {
  const name = getFilename(path);
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(0, dot) : name;
}

function getExtension(path: string): string {
  const name = getFilename(path);
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot).toLowerCase() : "";
}

function isImageFile(path: string): boolean {
  const ext = getExtension(path);
  return [".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp"].includes(ext);
}

function timeAgo(timestamp: string): string {
  const diff = Math.floor(
    (Date.now() - new Date(timestamp).getTime()) / 1000,
  );
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
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

// ── 3D Preview ──────────────────────────────────────────────────────────────

function PartModel({ url }: { url: string }) {
  const geometry = useLoader(STLLoader, url);
  const ref = useRef<Group>(null);

  const centered = useMemo(() => {
    geometry.computeBoundingBox();
    geometry.center();
    const box = geometry.boundingBox!;
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);
    if (maxDim > 0) geometry.scale(3 / maxDim, 3 / maxDim, 3 / maxDim);
    geometry.computeVertexNormals();
    return geometry;
  }, [geometry]);

  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.3;
  });

  return (
    <Center>
      <group ref={ref}>
        <mesh geometry={centered}>
          <meshStandardMaterial
            color="#cccccc"
            metalness={0.1}
            roughness={0.6}
            side={THREE.DoubleSide}
          />
        </mesh>
      </group>
    </Center>
  );
}

function PartPreview3D({ stem }: { stem: string }) {
  const stlPath = `stl/${stem}.stl`;
  if (!hasOfflineFile(stlPath)) {
    return <PreviewPlaceholder text="STL not available" />;
  }
  const meshUrl = fileUrl(stlPath);

  return (
    <div className="h-64 w-full rounded-base border-2 border-border bg-secondary-background overflow-hidden">
      <Canvas camera={{ position: [0, 0, 5], fov: 45 }}>
        <ambientLight intensity={0.4} />
        <directionalLight position={[5, 5, 5]} intensity={0.8} />
        <directionalLight position={[-3, 2, -2]} intensity={0.3} />
        <Environment preset="studio" />
        <Suspense fallback={null}>
          <PartModel url={meshUrl} />
        </Suspense>
        <OrbitControls enableDamping dampingFactor={0.1} />
      </Canvas>
    </div>
  );
}

// ── Other preview components ────────────────────────────────────────────────

function ImagePreview({ fileUrl, name }: { fileUrl: string; name: string }) {
  return (
    <div className="flex items-center justify-center rounded-base border-2 border-border bg-secondary-background p-2">
      <img src={fileUrl} alt={name} className="max-h-64 object-contain" />
    </div>
  );
}

interface DiffLine {
  type: "added" | "removed" | "unchanged";
  content: string;
  lineNo: number | null;
}

function computeDiff(oldText: string | null, newText: string): DiffLine[] {
  const newLines = newText.split("\n");
  if (oldText === null) {
    return newLines.map((line, i) => ({
      type: "added", content: line, lineNo: i + 1,
    }));
  }
  const oldLines = oldText.split("\n");
  const result: DiffLine[] = [];
  const maxLen = Math.max(oldLines.length, newLines.length);
  for (let i = 0; i < maxLen; i++) {
    const oldLine = i < oldLines.length ? oldLines[i] : undefined;
    const newLine = i < newLines.length ? newLines[i] : undefined;
    if (oldLine === newLine) {
      result.push({ type: "unchanged", content: newLine!, lineNo: i + 1 });
    } else {
      if (oldLine !== undefined)
        result.push({ type: "removed", content: oldLine, lineNo: null });
      if (newLine !== undefined)
        result.push({ type: "added", content: newLine, lineNo: i + 1 });
    }
  }
  return result;
}

function TextDiffPreview({
  content,
  previousContent,
}: {
  content: string;
  previousContent: string | null;
}) {
  const diffLines = computeDiff(previousContent, content);
  return (
    <div className="max-h-64 overflow-auto rounded-base border-2 border-border bg-secondary-background p-3">
      <pre className="text-xs leading-relaxed">
        {diffLines.map((line, i) => (
          <div
            key={i}
            className={
              line.type === "added"
                ? "bg-green-500/10 text-green-700 dark:text-green-400"
                : line.type === "removed"
                  ? "bg-red-500/10 text-red-700 dark:text-red-400"
                  : "text-foreground/70"
            }
          >
            <span className="mr-2 inline-block w-4 text-center select-none">
              {line.type === "added" ? "+" : line.type === "removed" ? "−" : " "}
            </span>
            <span className="mr-2 inline-block w-8 text-right text-foreground/30 select-none">
              {line.lineNo ?? ""}
            </span>
            {line.content}
          </div>
        ))}
      </pre>
    </div>
  );
}

function PreviewPlaceholder({ text }: { text?: string }) {
  return (
    <div className="flex h-48 items-center justify-center rounded-base border-2 border-border bg-secondary-background">
      <p className="text-sm text-foreground/40">{text ?? "No preview"}</p>
    </div>
  );
}

function ActivePreview({ event }: { event: WatchEvent }) {
  const eventFileUrl = fileUrl(event.relative_path);
  const name = getFilename(event.path);

  if (isImageFile(event.path)) {
    return <ImagePreview fileUrl={eventFileUrl} name={name} />;
  }
  if (event.content !== null) {
    return (
      <TextDiffPreview
        content={event.content}
        previousContent={event.previous_content}
      />
    );
  }
  return (
    <PreviewPlaceholder
      text={`Preview for ${getExtension(event.path) || event.type} files coming soon`}
    />
  );
}

// ── Active part card (grouped) ──────────────────────────────────────────────

function ActivePartCard({ group }: { group: PartGroup }) {
  const hasStl = group.formats.has("cadsmith/stl");

  return (
    <Card className="border-main">
      <CardHeader className="flex-row items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-base border-2 border-border bg-main">
          <Box className="size-5 text-main-foreground" />
        </div>
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-main opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-main" />
            </span>
            <CardTitle className="text-sm">{group.stem}</CardTitle>
          </div>
          <div className="flex items-center gap-1.5">
            {PART_FORMATS.map((fmt) => (
              <Badge
                key={fmt}
                variant={group.formats.has(fmt) ? "default" : "neutral"}
                className="text-[10px] px-1.5 py-0 uppercase"
              >
                {fmt}
              </Badge>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {hasStl ? (
          <PartPreview3D stem={group.stem} />
        ) : (
          <PreviewPlaceholder text="Waiting for STL file..." />
        )}
      </CardContent>
    </Card>
  );
}

// ── Progress tracking ──────────────────────────────────────────────────────

interface PartProgress {
  part_name: string;
  outputs: Record<string, { status: string; path: string | null }>;
}

function findProgressFiles(tree: FileNode[]): string[] {
  const paths: string[] = [];
  function walk(nodes: FileNode[]) {
    for (const node of nodes) {
      if (
        node.type === "file" &&
        node.path.startsWith("progress/") &&
        node.name.endsWith(".json")
      ) {
        paths.push(node.path);
      }
      if (node.children) walk(node.children);
    }
  }
  walk(tree);
  return paths.sort();
}

function useProgressData(treeVersion: number) {
  const fileTree = useFileTree(treeVersion);
  const [progress, setProgress] = useState<PartProgress[]>([]);

  const fetchProgress = useCallback(() => {
    const files = findProgressFiles(fileTree);
    if (files.length === 0) {
      setProgress([]);
      return;
    }
    Promise.all(files.map((p) => fetchJson<PartProgress>(p))).then((results) =>
      setProgress(results.filter(Boolean) as PartProgress[]),
    );
  }, [fileTree]);

  useEffect(() => {
    fetchProgress();
  }, [fetchProgress]);

  return progress;
}

const STATUS_COLORS: Record<string, string> = {
  done: "default",
  in_progress: "neutral",
  pending: "neutral",
  failed: "neutral",
};

function ProgressCard({ parts }: { parts: PartProgress[] }) {
  if (parts.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Build Progress</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {parts.map((part) => {
          const outputs = Object.entries(part.outputs);
          const total = outputs.length;
          const done = outputs.filter(([, v]) => v.status === "done").length;
          const pct = total > 0 ? Math.round((done / total) * 100) : 0;

          return (
            <div key={part.part_name} className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-sm font-heading">{part.part_name}</span>
                <span className="text-xs text-foreground/50">
                  {done}/{total}
                </span>
              </div>
              <Progress value={pct} />
              <div className="flex flex-wrap gap-1">
                {outputs.map(([name, info]) => (
                  <Badge
                    key={name}
                    variant={info.status === "done" ? "default" : info.status === "failed" ? "default" : "neutral"}
                    className="text-[9px] px-1.5 py-0"
                  >
                    {info.status === "failed" ? "✗ " : info.status === "done" ? "✓ " : ""}{name}
                  </Badge>
                ))}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

// ── Session log ────────────────────────────────────────────────────────────

interface LogEntry {
  timestamp: string;
  level: "info" | "warn" | "error" | "success";
  source: string;
  message: string;
  detail?: string;
}

function eventsToLogs(events: WatchEvent[]): LogEntry[] {
  return events.map((e) => {
    const meta = TYPE_META[e.type] ?? TYPE_META.unknown;
    const filename = e.relative_path?.split("/").pop() ?? "";
    return {
      timestamp: e.timestamp,
      level: "info" as const,
      source: meta.label.toLowerCase(),
      message: `${meta.verb} ${filename}`,
    };
  });
}

const LEVEL_STYLE: Record<string, string> = {
  info: "text-foreground/70",
  warn: "text-yellow-600 dark:text-yellow-400",
  error: "text-red-600 dark:text-red-400",
  success: "text-green-600 dark:text-green-400",
};

const LEVEL_BADGE: Record<string, "default" | "neutral"> = {
  info: "neutral",
  warn: "default",
  error: "default",
  success: "default",
};

function SessionLogCard({ logs }: { logs: LogEntry[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  if (logs.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Session Log</CardTitle>
      </CardHeader>
      <CardContent className="max-h-80 overflow-y-auto">
        <ul className="space-y-1">
          {logs.map((entry, i) => {
            const time = new Date(entry.timestamp);
            const timeStr = time.toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            });

            return (
              <li
                key={i}
                className={`flex items-start gap-2 text-xs ${LEVEL_STYLE[entry.level] ?? LEVEL_STYLE.info}`}
              >
                <span className="shrink-0 font-mono text-foreground/30">
                  {timeStr}
                </span>
                <Badge
                  variant={LEVEL_BADGE[entry.level] ?? "neutral"}
                  className="text-[9px] px-1 py-0 uppercase shrink-0"
                >
                  {entry.source}
                </Badge>
                <span className="break-words">
                  {entry.message}
                  {entry.detail && (
                    <span className="text-foreground/40 ml-1">
                      — {entry.detail}
                    </span>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
        <div ref={bottomRef} />
      </CardContent>
    </Card>
  );
}

// ── Main view ───────────────────────────────────────────────────────────────

export function ActiveView({ events, offline, treeVersion }: ActiveViewProps) {
  const asciiFrame = useRotatingAscii();
  const progressData = useProgressData(treeVersion);

  // Historical logs from file + live logs from events.
  const [historicalLogs, setHistoricalLogs] = useState<LogEntry[]>([]);
  useEffect(() => {
    fetchText("logs/session.jsonl")
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

  // Separate part events from non-part events.
  const { partGroups, nonPartEvents, latestNonPart } = useMemo(() => {
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
      latestNonPart: nonPart.length > 0 ? nonPart[nonPart.length - 1] : null,
    };
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

  // Filter to renderable event types: parts, assembly, manifest.
  const RENDERABLE_TYPES = new Set(["manifest", "assembly"]);
  const renderableNonPart = [...nonPartEvents]
    .reverse()
    .find((e) => RENDERABLE_TYPES.has(e.type)) ?? null;

  const latestEvent = events.length > 0 ? events[events.length - 1] : null;
  const latestIsPart = latestEvent ? getPartFormat(latestEvent) !== null : false;

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Offline info banner (non-blocking) */}
      {offline && (
        <Alert className="w-full">
          <AlertTitle>Offline mode</AlertTitle>
          <AlertDescription>
            Showing previously generated data. Start the GUI server for live
            updates.
          </AlertDescription>
        </Alert>
      )}

      {/* Active operation */}
      {latestIsPart && partGroups.length > 0 ? (
        <ActivePartCard group={partGroups[0]} />
      ) : renderableNonPart ? (
        <ActiveNonPartCard event={renderableNonPart} />
      ) : null}

      {/* Build progress */}
      <ProgressCard parts={progressData} />

      {/* Session log */}
      <SessionLogCard logs={sessionLogs} />
    </div>
  );
}

// ── Non-part active card ────────────────────────────────────────────────────

function ActiveNonPartCard({ event }: { event: WatchEvent }) {
  const meta = TYPE_META[event.type] ?? TYPE_META.unknown;
  const ActiveIcon = meta.icon;
  const showTree = event.type === "manifest" || event.type === "assembly";

  return (
    <Card className="border-main">
      <CardHeader className="flex-row items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-base border-2 border-border bg-main">
          <ActiveIcon className="size-5 text-main-foreground" />
        </div>
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-main opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-main" />
            </span>
            <CardTitle className="text-sm uppercase tracking-wide">
              {meta.verb}
            </CardTitle>
          </div>
          <p className="text-sm text-foreground">
            {getFilename(event.path)}
          </p>
        </div>
      </CardHeader>
      <CardContent>
        {showTree ? (
          <ComponentTreePreview />
        ) : (
          <>
            <ActivePreview event={event} />
            <p className="mt-2 truncate text-xs text-foreground/50">
              {event.path}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ComponentTreePreview() {
  const [treeData, setTreeData] = useState<any | null>(null);

  useEffect(() => {
    fetchJson("component_tree.json").then((data) => setTreeData(data));
  }, []);

  if (!treeData?.stages) return null;

  const comps: any[] = [];
  const walk = (nodes: any[]) => {
    for (const n of nodes) {
      comps.push(n);
      if (n.children) walk(n.children);
    }
  };
  for (const stage of treeData.stages) walk(stage.components);

  return (
    <div className="space-y-3">
      <RocketProfile stages={treeData.stages} />
      <ul className="space-y-1">
        {comps.map((comp) => {
          const fate = comp.agent?.fate ?? "unknown";
          const mass = comp.mass;
          const massStr = mass
            ? `${(mass[0] * (mass[1]?.includes("kilogram") ? 1000 : 1)).toFixed(1)} g`
            : null;
          return (
            <li key={comp.name} className="flex items-center gap-2 text-sm">
              <Badge
                variant={fate === "print" ? "default" : "neutral"}
                className="text-[9px] px-1.5 py-0 uppercase shrink-0"
              >
                {fate}
              </Badge>
              <span className="truncate">{comp.name}</span>
              <span className="text-xs text-foreground/40 shrink-0">{comp.type}</span>
              {massStr && (
                <span className="ml-auto text-xs text-foreground/50 shrink-0">{massStr}</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

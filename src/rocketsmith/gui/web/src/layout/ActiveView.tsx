import { Suspense, useRef, useMemo } from "react";
import { apiBase } from "@/lib/server";
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

interface ActiveViewProps {
  events: WatchEvent[];
  offline: boolean;
}

const TYPE_META: Record<
  string,
  { icon: typeof Box; label: string; verb: string }
> = {
  parts: { icon: Box, label: "PART", verb: "Generating" },
  flight: { icon: LineChart, label: "FLIGHT", verb: "Running flight" },
  assembly: { icon: Box, label: "ASSEMBLY", verb: "Building assembly" },
  report: { icon: FileText, label: "REPORT", verb: "Reporting" },
  manifest: { icon: Package, label: "MANIFEST", verb: "Building manifest" },
  gcode: { icon: Printer, label: "GCODE", verb: "Slicing" },
  script: { icon: Cog, label: "SCRIPT", verb: "Running script" },
  unknown: { icon: Cog, label: "FILE", verb: "Processing" },
};

/** Part format extensions we track for grouped badges. */
const PART_FORMATS = ["cadsmith", "step", "stl", "png", "gif"] as const;

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
 * Check if an event is a part file (lives under parts/<format>/).
 * Returns the format subfolder name or null.
 */
function getPartFormat(event: WatchEvent): string | null {
  const rel = event.relative_path;
  if (!rel.startsWith("parts/")) return null;
  const parts = rel.split("/");
  // parts/<format>/<file>
  if (parts.length >= 3) return parts[1];
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
  const meshUrl = `${apiBase()}/api/files/parts/stl/${stem}.stl`;

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
  const fileUrl = `${apiBase()}/api/files/${event.relative_path}`;
  const name = getFilename(event.path);

  if (isImageFile(event.path)) {
    return <ImagePreview fileUrl={fileUrl} name={name} />;
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
  const hasStl = group.formats.has("stl");

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

// ── Main view ───────────────────────────────────────────────────────────────

export function ActiveView({ events, offline }: ActiveViewProps) {
  const asciiFrame = useRotatingAscii();

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

  if (offline || events.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <pre className="select-none text-[3px] leading-[3px] font-semibold text-foreground/20 sm:text-[4px] sm:leading-[4px] xl:text-[6px] xl:leading-[6px]">
            {asciiFrame}
          </pre>
          <div className="text-center">
            <p className="text-sm font-heading text-foreground/40">
              {offline ? "Offline mode" : "Waiting for activity..."}
            </p>
            <p className="mt-1 text-xs text-foreground/30">
              {offline
                ? "Start the GUI server to enable live updates"
                : "The agent hasn't started yet"}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Determine what to show as the "active" card.
  // If the latest event overall is a part event, show the part card.
  // Otherwise show the non-part active card.
  const latestEvent = events[events.length - 1];
  const latestIsPart = getPartFormat(latestEvent) !== null;

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto">
      {/* Active operation */}
      {latestIsPart && partGroups.length > 0 ? (
        <ActivePartCard group={partGroups[0]} />
      ) : latestNonPart ? (
        <ActiveNonPartCard event={latestNonPart} />
      ) : null}

      {/* Recent activity — parts grouped, non-parts listed */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Recent Activity</CardTitle>
        </CardHeader>
        <CardContent className="max-h-64 overflow-y-auto">
          <ul className="space-y-2">
            {/* Part groups */}
            {partGroups.slice(latestIsPart ? 1 : 0).map((g) => (
              <li
                key={`part-${g.stem}`}
                className="flex items-center gap-2 text-sm text-foreground/70"
              >
                <Box className="size-3.5 shrink-0" />
                <span className="truncate">{g.stem}</span>
                <div className="flex items-center gap-1 ml-auto shrink-0">
                  {PART_FORMATS.map((fmt) => (
                    <Badge
                      key={fmt}
                      variant={g.formats.has(fmt) ? "default" : "neutral"}
                      className="text-[9px] px-1 py-0 uppercase"
                    >
                      {fmt}
                    </Badge>
                  ))}
                </div>
              </li>
            ))}

            {/* Non-part events */}
            {[...nonPartEvents]
              .reverse()
              .slice(latestIsPart ? 0 : 1)
              .map((e, i) => {
                const m = TYPE_META[e.type] ?? TYPE_META.unknown;
                const Icon = m.icon;
                return (
                  <li
                    key={`evt-${i}`}
                    className="flex items-center gap-2 text-sm text-foreground/70"
                  >
                    <Icon className="size-3.5 shrink-0" />
                    <Badge
                      variant="neutral"
                      className="text-[10px] px-1.5 py-0"
                    >
                      {m.label}
                    </Badge>
                    <span className="truncate">{getFilename(e.path)}</span>
                    <span className="ml-auto shrink-0 text-xs text-foreground/40">
                      {timeAgo(e.timestamp)}
                    </span>
                  </li>
                );
              })}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Non-part active card ────────────────────────────────────────────────────

function ActiveNonPartCard({ event }: { event: WatchEvent }) {
  const meta = TYPE_META[event.type] ?? TYPE_META.unknown;
  const ActiveIcon = meta.icon;

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
        <ActivePreview event={event} />
        <p className="mt-2 truncate text-xs text-foreground/50">
          {event.path}
        </p>
      </CardContent>
    </Card>
  );
}

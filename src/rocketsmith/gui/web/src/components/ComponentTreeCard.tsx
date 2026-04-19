import { memo, useEffect, useState } from "react";
import { Network, CircleDot, CirclePlus, Box, Umbrella, Wrench, Flame, Cpu } from "lucide-react";
import { fetchJson, getOfflineFilesTree } from "@/lib/server";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { RocketProfile } from "@/components/RocketProfile";
import type { Stage, ComponentNode } from "@/components/RocketProfile";

type Qty = [number, string];

interface ComponentTree {
  schema_version: number;
  rocket_name: string;
  generated_at: string;
  stages: Stage[];
}

const FATE_VARIANT: Record<string, "default" | "neutral"> = {
  print: "default",
  fuse: "neutral",
  purchase: "neutral",
  skip: "neutral",
};

// Category → icon + color
const CATEGORY_ICON: Record<string, React.ReactNode> = {
  structural:  <Box      className="size-3 shrink-0 text-blue-400"   />,
  recovery:    <Umbrella className="size-3 shrink-0 text-green-400"  />,
  hardware:    <Wrench   className="size-3 shrink-0 text-orange-400" />,
  propulsion:  <Flame    className="size-3 shrink-0 text-red-400"    />,
  electronics: <Cpu      className="size-3 shrink-0 text-purple-400" />,
};

function fmtMass(q: Qty | null): string {
  if (!q) return "";
  const [val, unit] = q;
  if (unit.includes("kilogram")) return `${(val * 1000).toFixed(1)} g`;
  return `${val.toFixed(1)} g`;
}

/** Extract the most useful dimension summary for a component type. */
function fmtDims(type: string, dims: Record<string, unknown>): string {
  function mm(key: string): number {
    const v = dims[key];
    if (Array.isArray(v)) return v[0] as number;
    if (typeof v === "number") return v;
    return 0;
  }
  function str(n: number): string { return n > 0 ? n.toFixed(0) : "?"; }

  switch (type) {
    case "RailButton": {
      const od = mm("outer_diameter"); const n = (dims.instance_count as number) ?? 1;
      return `×${n} ⌀${str(od)} mm`;
    }
    case "LaunchLug": {
      const od = mm("outer_diameter"); const len = mm("length");
      return `⌀${str(od)} × ${str(len)} mm`;
    }
    case "CenteringRing":
    case "BulkHead":
    case "EngineBlock": {
      const od = mm("od"); const t = mm("thickness");
      return `⌀${str(od)} t${str(t)} mm`;
    }
    case "Parachute": {
      const d = mm("diameter");
      return d > 0 ? `⌀${str(d)} mm` : "";
    }
    case "Streamer": {
      const len = mm("length"); const w = mm("width");
      return len > 0 ? `${str(len)} × ${str(w)} mm` : "";
    }
    case "ShockCord": {
      const len = mm("length");
      return len > 0 ? `${str(len)} mm` : "";
    }
    case "TrapezoidFinSet":
    case "EllipticalFinSet":
    case "FreeformFinSet": {
      const n = (dims.count as number) ?? 0; const span = mm("span");
      return n > 0 ? `×${n}  ${str(span)} mm span` : "";
    }
    default:
      return "";
  }
}

function countComponents(nodes: ComponentNode[]): number {
  let count = 0;
  for (const n of nodes) {
    count += 1 + countComponents(n.children);
  }
  return count;
}

// ── Tree row with indent lines ────────────────────────────────────────────

function ComponentRow({
  node,
  depth,
  isLast,
  parentLines,
  hoveredName,
  onHover,
}: {
  node: ComponentNode;
  depth: number;
  isLast: boolean;
  parentLines: boolean[];
  hoveredName: string | null;
  onHover: (name: string | null) => void;
}) {
  const fate = node.agent?.fate ?? "unknown";
  const isHighlighted = hoveredName === node.name;

  return (
    <>
      <li
        className={`flex items-center gap-2 text-sm cursor-default rounded-sm transition-colors ${
          isHighlighted ? "bg-main/10" : ""
        }`}
        onMouseEnter={() => onHover(node.name)}
        onMouseLeave={() => onHover(null)}
      >
        <div className="flex shrink-0" style={{ width: `${depth * 20}px` }}>
          {parentLines.map((showLine, i) => (
            <span
              key={i}
              className="inline-block w-5 shrink-0 self-stretch"
              style={{
                borderLeft: showLine ? "1px solid var(--border)" : "none",
              }}
            />
          ))}
        </div>
        {depth > 0 && (
          <span className="inline-flex items-center shrink-0 text-foreground/30 text-xs font-mono -ml-2 w-5">
            {isLast ? "└─" : "├─"}
          </span>
        )}
        {CATEGORY_ICON[node.category] ?? null}
        <Badge
          variant={FATE_VARIANT[fate] ?? "neutral"}
          className="text-[9px] px-1.5 py-0 uppercase shrink-0"
        >
          {fate}
        </Badge>
        <span className="font-heading truncate">{node.name}</span>
        <span className="text-xs text-foreground/40 shrink-0">{node.type}</span>
        <span className="ml-auto flex items-center gap-2 shrink-0">
          {(() => {
            const dimStr = fmtDims(node.type, node.dimensions as Record<string, unknown>);
            return dimStr ? (
              <span className="text-xs text-foreground/35 font-mono">{dimStr}</span>
            ) : null;
          })()}
          {node.mass && (
            <span className="text-xs text-foreground/50">{fmtMass(node.mass)}</span>
          )}
        </span>
      </li>
      {node.children.map((child, i) => (
        <ComponentRow
          key={child.name}
          node={child}
          depth={depth + 1}
          isLast={i === node.children.length - 1}
          parentLines={[...parentLines, !isLast]}
          hoveredName={hoveredName}
          onHover={onHover}
        />
      ))}
    </>
  );
}

// ── Main card ─────────────────────────────────────────────────────────────

interface ComponentTreeCardProps {
  className?: string;
  /** Bumped by the parent whenever the offline data bundle is refreshed. */
  treeVersion?: number;
}

export const ComponentTreeCard = memo(function ComponentTreeCard({ className, treeVersion = 0 }: ComponentTreeCardProps) {
  const [tree, setTree] = useState<ComponentTree | null>(null);
  const [cgMm, setCgMm] = useState<number | null>(null);
  const [cpMm, setCpMm] = useState<number | null>(null);
  const [stabilityCal, setStabilityCal] = useState<number | null>(null);
  const [hoveredName, setHoveredName] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<ComponentTree>("gui/component_tree.json").then((data) => {
      setTree(data);
      if (!data?.stages?.length) return;

      // Read CG/CP/stability from the first stage (static Barrowman values).
      const stage = data.stages[0];
      const cg = stage.cg as Qty | null;
      const cp = stage.cp as Qty | null;
      if (cg) setCgMm(cg[0]);
      if (cp) setCpMm(cp[0]);
      if (stage.stability_cal != null) setStabilityCal(stage.stability_cal);

      // If static values are present, skip the flight timeseries lookup.
      if (cg && cp) return;

      // Fallback: fetch CG/CP from flight timeseries data.
      (async () => {
        try {
          const fileTree = (getOfflineFilesTree() as any[]) ?? [];
          const orDir = fileTree.find((n: any) => n.name === "openrocket");
          const flightsDir = orDir?.children?.find(
            (n: any) => n.name === "flights",
          );
          const flightFile = flightsDir?.children?.find((n: any) =>
            n.name.endsWith(".json"),
          );
          if (!flightFile) return;

          const flight = await fetchJson<any>(flightFile.path);
          if (!flight?.timeseries) return;

          const cgTs = flight.timeseries.TYPE_CG_LOCATION as number[];
          const cpTs = flight.timeseries.TYPE_CP_LOCATION as number[];

          if (!cg && cgTs) {
            for (let i = 10; i < cgTs.length; i++) {
              if (cgTs[i] != null && cgTs[i] === cgTs[i]) {
                setCgMm(cgTs[i] * 1000);
                break;
              }
            }
          }
          if (!cp && cpTs) {
            for (let i = 10; i < cpTs.length; i++) {
              if (cpTs[i] != null && cpTs[i] === cpTs[i]) {
                setCpMm(cpTs[i] * 1000);
                break;
              }
            }
          }

          if (stage.stability_cal == null) {
            const stab = flight.timeseries.TYPE_STABILITY as number[];
            if (stab) {
              for (let i = 10; i < stab.length; i++) {
                if (stab[i] != null && stab[i] === stab[i]) {
                  setStabilityCal(stab[i]);
                  break;
                }
              }
            }
          }
        } catch {}
      })();
    });
  }, [treeVersion]);

  if (!tree?.stages) {
    return (
      <Card className={className ?? "h-full"}>
        <CardHeader className="shrink-0">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Network className="size-4" /> Component Tree
          </CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center">
          <p className="text-sm text-foreground/40">No component tree yet</p>
        </CardContent>
      </Card>
    );
  }

  const totalComponents = tree.stages.reduce(
    (n, s) => n + countComponents(s.components),
    0,
  );

  return (
    <Card className={`${className ?? "h-full"} flex flex-col`}>
      <CardHeader className="shrink-0 space-y-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Network className="size-4" /> Component Tree
        </CardTitle>
        <div className="flex flex-wrap gap-2 items-center">
          <div className="flex items-center gap-1.5">
            <Badge variant="neutral" className="text-[10px] px-1.5 py-0">
              Rocket
            </Badge>
            <span className="text-sm font-heading">{tree.rocket_name}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Badge variant="neutral" className="text-[10px] px-1.5 py-0">
              Stages
            </Badge>
            <span className="text-sm font-heading">{tree.stages.length}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Badge variant="neutral" className="text-[10px] px-1.5 py-0">
              Components
            </Badge>
            <span className="text-sm font-heading">{totalComponents}</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-y-auto space-y-3">
        {/* Rocket profile visualization */}
        <RocketProfile stages={tree.stages} cgMm={cgMm} cpMm={cpMm} highlightedName={hoveredName} />

        {/* CG / CP / Stability */}
        {(cgMm !== null || cpMm !== null || stabilityCal !== null) && (
          <div className="flex flex-wrap gap-2 items-center">
            {cgMm !== null && (
              <div className="flex items-center gap-1.5">
                <Badge variant="neutral" className="text-[10px] px-1.5 py-0 gap-1">
                  <CirclePlus className="size-3" />
                  CG
                </Badge>
                <span className="text-sm font-heading">
                  {cgMm.toFixed(0)} mm
                </span>
              </div>
            )}
            {cpMm !== null && (
              <div className="flex items-center gap-1.5">
                <Badge variant="neutral" className="text-[10px] px-1.5 py-0 gap-1">
                  <CircleDot className="size-3" />
                  CP
                </Badge>
                <span className="text-sm font-heading">
                  {cpMm.toFixed(0)} mm
                </span>
              </div>
            )}
            {stabilityCal !== null && (
              <div className="flex items-center gap-1.5">
                <Badge variant="neutral" className="text-[10px] px-1.5 py-0">
                  Stability
                </Badge>
                <span className="text-sm font-heading">
                  {stabilityCal.toFixed(2)} cal
                </span>
              </div>
            )}
          </div>
        )}

        {/* Component list per stage */}
        {tree.stages.map((stage) => (
          <ul key={stage.name} className="space-y-0.5">
            {stage.components.map((comp, i) => (
              <ComponentRow
                key={comp.name}
                node={comp}
                depth={0}
                isLast={i === stage.components.length - 1}
                parentLines={[]}
                hoveredName={hoveredName}
                onHover={setHoveredName}
              />
            ))}
          </ul>
        ))}
      </CardContent>
    </Card>
  );
});

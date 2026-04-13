import { useEffect, useState } from "react";
import { Network, CircleDot, CirclePlus } from "lucide-react";
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

function fmtMass(q: Qty | null): string {
  if (!q) return "";
  const [val, unit] = q;
  if (unit.includes("kilogram")) return `${(val * 1000).toFixed(1)} g`;
  return `${val.toFixed(1)} g`;
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
}: {
  node: ComponentNode;
  depth: number;
  isLast: boolean;
  parentLines: boolean[];
}) {
  const fate = node.agent?.fate ?? "unknown";

  return (
    <>
      <li className="flex items-center gap-2 text-sm">
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
        <Badge
          variant={FATE_VARIANT[fate] ?? "neutral"}
          className="text-[9px] px-1.5 py-0 uppercase shrink-0"
        >
          {fate}
        </Badge>
        <span className="font-heading truncate">{node.name}</span>
        <span className="text-xs text-foreground/40 shrink-0">{node.type}</span>
        {node.mass && (
          <span className="ml-auto text-xs text-foreground/50 shrink-0">
            {fmtMass(node.mass)}
          </span>
        )}
      </li>
      {node.children.map((child, i) => (
        <ComponentRow
          key={child.name}
          node={child}
          depth={depth + 1}
          isLast={i === node.children.length - 1}
          parentLines={[...parentLines, !isLast]}
        />
      ))}
    </>
  );
}

// ── Main card ─────────────────────────────────────────────────────────────

interface ComponentTreeCardProps {
  className?: string;
}

export function ComponentTreeCard({ className }: ComponentTreeCardProps) {
  const [tree, setTree] = useState<ComponentTree | null>(null);
  const [cgMm, setCgMm] = useState<number | null>(null);
  const [cpMm, setCpMm] = useState<number | null>(null);
  const [stabilityCal, setStabilityCal] = useState<number | null>(null);

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
  }, []);

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
        <RocketProfile stages={tree.stages} cgMm={cgMm} cpMm={cpMm} />

        {/* CG / CP / Stability */}
        {(cgMm !== null || cpMm !== null || stabilityCal !== null) && (
          <div className="flex flex-wrap gap-2 items-center">
            {cgMm !== null && (
              <div className="flex items-center gap-1.5">
                <Badge
                  className="text-[10px] px-1.5 py-0 text-white gap-1"
                  style={{ backgroundColor: "#3b82f6" }}
                >
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
                <Badge
                  className="text-[10px] px-1.5 py-0 text-white gap-1"
                  style={{ backgroundColor: "#ef4444" }}
                >
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
              />
            ))}
          </ul>
        ))}
      </CardContent>
    </Card>
  );
}

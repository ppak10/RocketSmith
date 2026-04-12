import { useEffect, useState } from "react";
import { fetchJson, getOfflineFilesTree } from "@/lib/server";
import { CircleDot, CirclePlus } from "lucide-react";
import { RocketProfile } from "@/components/RocketProfile";
import type { Stage, ComponentNode } from "@/components/RocketProfile";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

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

function mag(q: Qty): number {
  return q[0];
}

function fmtQty(q: Qty | null): string {
  if (!q) return "—";
  return `${q[0].toFixed(1)} ${q[1].split(" / ")[0].replace("millimeter", "mm").replace("kilogram", "kg").replace("gram", "g")}`;
}

function fmtMass(q: Qty | null): string {
  if (!q) return "—";
  const [val, unit] = q;
  if (unit.includes("kilogram")) return `${(val * 1000).toFixed(1)} g`;
  return `${val.toFixed(1)} g`;
}

// ── Component tree rows ────────────────────────────────────────────────────

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
        {/* Tree lines */}
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

export function ComponentTreeViewer() {
  const [tree, setTree] = useState<ComponentTree | null>(null);
  const [loading, setLoading] = useState(true);
  const [cgMm, setCgMm] = useState<number | null>(null);
  const [cpMm, setCpMm] = useState<number | null>(null);
  const [stabilityCal, setStabilityCal] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchJson<ComponentTree>("component_tree.json")
      .then((data) => {
        setTree(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));

    // Fetch CG/CP from the first available flight JSON.
    (async () => {
      try {
        const fileTree = (getOfflineFilesTree() as any[]) ?? [];
        const orDir = fileTree.find((n: any) => n.name === "openrocket");
        const flightsDir = orDir?.children?.find((n: any) => n.name === "flights");
        const flightFile = flightsDir?.children?.find((n: any) => n.name.endsWith(".json"));
        if (!flightFile) return;

        const flight = await fetchJson<any>(flightFile.path);
        if (!flight) return;
        if (!flight?.timeseries) return;

        const cg = flight.timeseries.TYPE_CG_LOCATION as number[];
        const cp = flight.timeseries.TYPE_CP_LOCATION as number[];
        if (!cg || !cp) return;

        // Find first valid (non-null/NaN) values after liftoff.
        for (let i = 10; i < Math.min(cg.length, cp.length); i++) {
          if (cg[i] != null && cg[i] === cg[i]) { setCgMm(cg[i] * 1000); break; }
        }
        for (let i = 10; i < cp.length; i++) {
          if (cp[i] != null && cp[i] === cp[i]) { setCpMm(cp[i] * 1000); break; }
        }

        const stab = flight.timeseries.TYPE_STABILITY as number[];
        if (stab) {
          for (let i = 10; i < stab.length; i++) {
            if (stab[i] != null && stab[i] === stab[i]) { setStabilityCal(stab[i]); break; }
          }
        }
      } catch {}
    })();
  }, []);

  if (loading) {
    return (
      <Card className="h-full">
        <CardContent className="flex h-full items-center justify-center">
          <p className="text-sm text-foreground/40">Loading component tree...</p>
        </CardContent>
      </Card>
    );
  }

  if (!tree) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="text-sm">Component Tree</CardTitle>
        </CardHeader>
        <CardContent className="flex h-48 items-center justify-center">
          <p className="text-sm text-foreground/40">
            No component tree found. Run the manufacturing agent to generate it.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <Card className="py-0 gap-0">
        <CardContent className="p-0">
          <RocketProfile stages={tree.stages} cgMm={cgMm} cpMm={cpMm} />
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-3 items-center">
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
          <span className="text-sm font-heading">
            {tree.stages.reduce((n, s) => n + countComponents(s.components), 0)}
          </span>
        </div>
        <div className="ml-auto flex gap-3">
          {cgMm !== null && (
            <div className="flex items-center gap-1.5">
              <Badge className="text-[10px] px-1.5 py-0 text-white gap-1" style={{ backgroundColor: "#3b82f6" }}>
                <CirclePlus className="size-3" />
                CG
              </Badge>
              <span className="text-sm font-heading">{cgMm.toFixed(0)} mm</span>
            </div>
          )}
          {cpMm !== null && (
            <div className="flex items-center gap-1.5">
              <Badge className="text-[10px] px-1.5 py-0 text-white gap-1" style={{ backgroundColor: "#ef4444" }}>
                <CircleDot className="size-3" />
                CP
              </Badge>
              <span className="text-sm font-heading">{cpMm.toFixed(0)} mm</span>
            </div>
          )}
          {stabilityCal !== null && (
            <div className="flex items-center gap-1.5">
              <Badge variant="neutral" className="text-[10px] px-1.5 py-0">
                Stability
              </Badge>
              <span className="text-sm font-heading">{stabilityCal.toFixed(2)} cal</span>
            </div>
          )}
        </div>
      </div>

      {tree.stages.map((stage) => (
        <Card key={stage.name} className="gap-0">
          <CardContent>
            <ul className="space-y-0.5">
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
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function countComponents(nodes: ComponentNode[]): number {
  let count = 0;
  for (const n of nodes) {
    count += 1 + countComponents(n.children);
  }
  return count;
}

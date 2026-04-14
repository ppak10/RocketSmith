import { memo, useEffect, useMemo, useState } from "react";
import { Rocket } from "lucide-react";
import { fetchJson, hasOfflineFile } from "@/lib/server";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useFileTree } from "@/hooks/useFileTree";
import type { FileNode } from "@/hooks/useFileTree";

interface FlightData {
  flight_name: string;
  config: string;
  summary: {
    max_altitude_m: number;
    max_velocity_ms: number;
    time_to_apogee_s: number | null;
    flight_time_s: number;
    min_stability_cal: number | null;
    max_stability_cal: number | null;
  };
  timeseries: Record<string, number[]>;
  events: Record<string, number[]>;
}

function normalizeFlightData(raw: Record<string, unknown>): FlightData {
  return {
    ...raw,
    flight_name: (raw.flight_name ?? raw.simulation_name ?? "Unknown") as string,
  } as FlightData;
}

function findFlightFiles(tree: FileNode[]): string[] {
  const paths: string[] = [];
  function walk(nodes: FileNode[]) {
    for (const node of nodes) {
      if (
        node.type === "file" &&
        (node.path.startsWith("openrocket/flights/") ||
          node.path.startsWith("openrocket/simulations/")) &&
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

const CHARTS = [
  { id: "altitude", title: "Altitude", yKey: "TYPE_ALTITUDE", yLabel: "m" },
  { id: "velocity", title: "Velocity", yKey: "TYPE_VELOCITY_TOTAL", yLabel: "m/s" },
  { id: "stability", title: "Stability", yKey: "TYPE_STABILITY", yLabel: "cal" },
  { id: "thrust", title: "Thrust", yKey: "TYPE_THRUST_FORCE", yLabel: "N" },
];

interface FlightCardProps {
  className?: string;
  treeVersion?: number;
}

export const FlightCard = memo(function FlightCard({
  className,
  treeVersion = 0,
}: FlightCardProps) {
  const fileTree = useFileTree(treeVersion);
  const [simulations, setSimulations] = useState<FlightData[]>([]);
  const [activeSim, setActiveSim] = useState("");
  const [activeChart, setActiveChart] = useState("altitude");

  useEffect(() => {
    const simFiles = findFlightFiles(fileTree);
    if (simFiles.length === 0) {
      setSimulations([]);
      return;
    }

    Promise.all(
      simFiles.map((path) => fetchJson<Record<string, unknown>>(path)),
    ).then((results) => {
      const valid = (results.filter(Boolean) as Record<string, unknown>[]).map(
        normalizeFlightData,
      );
      setSimulations(valid);
      if (valid.length > 0 && !valid.find((s) => s.flight_name === activeSim)) {
        setActiveSim(valid[0].flight_name);
      }
    });
  }, [fileTree, treeVersion]);

  const currentSim = simulations.find((s) => s.flight_name === activeSim);

  if (simulations.length === 0) {
    return (
      <Card className={className ?? "h-full"}>
        <CardHeader className="shrink-0">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Rocket className="size-4" /> Flight Simulation
          </CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center">
          <p className="text-sm text-foreground/40">No flight data yet</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`${className ?? "h-full"} flex flex-col`}>
      <CardHeader className="shrink-0 space-y-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Rocket className="size-4" /> Flight Simulation
        </CardTitle>

        {/* Sim selector (if multiple) */}
        {simulations.length > 1 && (
          <Tabs value={activeSim} onValueChange={setActiveSim}>
            <TabsList className="h-7">
              {simulations.map((sim) => (
                <TabsTrigger
                  key={sim.flight_name}
                  value={sim.flight_name}
                  className="text-[10px] px-2 py-0.5"
                >
                  {sim.flight_name}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        )}

        {/* Summary badges */}
        {currentSim && <SummaryBadges summary={currentSim.summary} />}
      </CardHeader>
      <CardContent className="min-h-0 flex-1 flex flex-col gap-2">
        {/* Chart selector */}
        <Tabs value={activeChart} onValueChange={setActiveChart}>
          <TabsList className="h-7">
            {CHARTS.map((c) => (
              <TabsTrigger
                key={c.id}
                value={c.id}
                className="text-[10px] px-2 py-0.5"
              >
                {c.title}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {/* Chart */}
        {currentSim && <MiniChart sim={currentSim} chartId={activeChart} />}
      </CardContent>
    </Card>
  );
});

function SummaryBadges({ summary }: { summary: FlightData["summary"] }) {
  const items = [
    { label: "Apogee", value: `${summary.max_altitude_m.toFixed(1)} m` },
    { label: "Vmax", value: `${summary.max_velocity_ms.toFixed(1)} m/s` },
    {
      label: "T-apogee",
      value: summary.time_to_apogee_s
        ? `${summary.time_to_apogee_s.toFixed(1)} s`
        : "\u2014",
    },
    { label: "Duration", value: `${summary.flight_time_s.toFixed(1)} s` },
    {
      label: "Stability",
      value:
        summary.min_stability_cal != null && summary.max_stability_cal != null
          ? `${summary.min_stability_cal.toFixed(2)}\u2013${summary.max_stability_cal.toFixed(2)} cal`
          : "\u2014",
    },
  ];

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1">
          <Badge variant="neutral" className="text-[9px] px-1.5 py-0">
            {item.label}
          </Badge>
          <span className="text-xs font-heading">{item.value}</span>
        </div>
      ))}
    </div>
  );
}

function MiniChart({ sim, chartId }: { sim: FlightData; chartId: string }) {
  const chart = CHARTS.find((c) => c.id === chartId) ?? CHARTS[0];
  const time = sim.timeseries.TYPE_TIME;
  const yData = sim.timeseries[chart.yKey];

  if (!time || !yData) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-xs text-foreground/40">No {chart.title.toLowerCase()} data</p>
      </div>
    );
  }

  const data = useMemo(
    () =>
      time.map((t, i) => ({
        time: parseFloat(t.toFixed(3)),
        value: parseFloat(yData[i]?.toFixed(4) ?? "0"),
      })),
    [time, yData],
  );

  const apogee = sim.events.APOGEE?.[0];
  const burnout = sim.events.BURNOUT?.[0];

  const chartConfig: ChartConfig = {
    value: { label: "", color: "var(--chart-1)" },
  };

  return (
    <ChartContainer config={chartConfig} className="min-h-0 flex-1 w-full">
      <LineChart data={data}>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="var(--border)"
          opacity={0.3}
        />
        <XAxis
          dataKey="time"
          type="number"
          domain={["dataMin", "dataMax"]}
          tick={{ fontSize: 9 }}
          label={{
            value: "s",
            position: "insideBottomRight",
            offset: -5,
            fontSize: 9,
          }}
        />
        <YAxis
          tick={{ fontSize: 9 }}
          label={{
            value: chart.yLabel,
            position: "insideTopLeft",
            offset: -5,
            fontSize: 9,
          }}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              hideLabel
              hideIndicator={false}
              indicator="dot"
              formatter={(value: number | string) => (
                <>
                  <div
                    className="size-2.5 shrink-0 rounded-[2px] border border-border"
                    style={{ backgroundColor: "var(--color-value)" }}
                  />
                  <span className="text-foreground font-mono font-medium tabular-nums">
                    {value} {chart.yLabel}
                  </span>
                </>
              )}
            />
          }
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke="var(--color-value)"
          strokeWidth={1.5}
          dot={false}
        />
        {burnout != null && (
          <ReferenceLine
            x={parseFloat(burnout.toFixed(3))}
            stroke="var(--chart-5)"
            strokeDasharray="4 4"
            label={{
              value: "BURNOUT",
              position: "insideTopLeft",
              fontSize: 8,
              fill: "var(--chart-5)",
            }}
          />
        )}
        {apogee != null && (
          <ReferenceLine
            x={parseFloat(apogee.toFixed(3))}
            stroke="var(--chart-4)"
            strokeDasharray="4 4"
            label={{
              value: "APOGEE",
              position: "insideTopRight",
              fontSize: 8,
              fill: "var(--chart-4)",
            }}
          />
        )}
      </LineChart>
    </ChartContainer>
  );
}

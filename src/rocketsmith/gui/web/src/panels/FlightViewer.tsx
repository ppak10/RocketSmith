import { useEffect, useState } from "react";
import { apiBase } from "@/lib/server";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { useFileTree } from "@/hooks/useFileTree";
import type { FileNode } from "@/hooks/useFileTree";
import type { WatchEvent } from "@/hooks/useWatchSocket";

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

/** Normalize legacy simulation_name to flight_name. */
function normalizeFlightData(raw: Record<string, unknown>): FlightData {
  return {
    ...raw,
    flight_name: (raw.flight_name ?? raw.simulation_name ?? "Unknown") as string,
  } as FlightData;
}

const CHARTS = [
  { id: "altitude", title: "Altitude", yKey: "TYPE_ALTITUDE", yLabel: "m" },
  { id: "velocity", title: "Velocity", yKey: "TYPE_VELOCITY_TOTAL", yLabel: "m/s" },
  { id: "acceleration", title: "Acceleration", yKey: "TYPE_ACCELERATION_TOTAL", yLabel: "m/s²" },
  { id: "stability", title: "Stability", yKey: "TYPE_STABILITY", yLabel: "cal" },
  { id: "thrust", title: "Thrust", yKey: "TYPE_THRUST_FORCE", yLabel: "N" },
  { id: "drag", title: "Drag Coeff", yKey: "TYPE_DRAG_COEFF", yLabel: "Cd" },
];

interface FlightViewerProps {
  events: WatchEvent[];
}

/** Walk the file tree to find flight JSONs under openrocket/flights/ or openrocket/simulations/. */
function findFlightFiles(
  tree: FileNode[],
): string[] {
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

export function FlightViewer({ events }: FlightViewerProps) {
  const fileTree = useFileTree(events);
  const [simulations, setSimulations] = useState<FlightData[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeSim, setActiveSim] = useState("");

  useEffect(() => {
    setLoading(true);
    const simFiles = findFlightFiles(fileTree);

    if (simFiles.length === 0) {
      setSimulations([]);
      setLoading(false);
      return;
    }

    Promise.all(
      simFiles.map((path) =>
        fetch(`${apiBase()}/api/files/${path}`)
          .then((r) => (r.ok ? r.json() : null))
          .catch(() => null),
      ),
    ).then((results) => {
      const valid = results.filter(Boolean).map(normalizeFlightData);
      setSimulations(valid);
      if (valid.length > 0) setActiveSim(valid[0].flight_name);
      setLoading(false);
    });
  }, [fileTree]);

  if (loading) {
    return (
      <Card className="h-full">
        <CardContent className="flex h-full items-center justify-center">
          <p className="text-sm text-foreground/40">Loading flight data...</p>
        </CardContent>
      </Card>
    );
  }

  if (simulations.length === 0) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="text-sm">Flights</CardTitle>
        </CardHeader>
        <CardContent className="flex h-48 items-center justify-center">
          <p className="text-sm text-foreground/40">
            No flight data found. Run openrocket_flight(action="run") to generate it.
          </p>
        </CardContent>
      </Card>
    );
  }

  const currentSim = simulations.find((s) => s.flight_name === activeSim);

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto">
      <Tabs value={activeSim} onValueChange={setActiveSim}>
        <TabsList>
          {simulations.map((sim) => (
            <TabsTrigger key={sim.flight_name} value={sim.flight_name}>
              {sim.flight_name}
            </TabsTrigger>
          ))}
        </TabsList>

        {simulations.map((sim) => (
          <TabsContent key={sim.flight_name} value={sim.flight_name}>
            <SummaryCard summary={sim.summary} />
          </TabsContent>
        ))}
      </Tabs>

      {currentSim && <SimCharts sim={currentSim} />}
    </div>
  );
}

function SummaryCard({ summary }: { summary: FlightData["summary"] }) {
  const items = [
    { label: "Max Altitude", value: `${summary.max_altitude_m.toFixed(1)} m` },
    { label: "Max Velocity", value: `${summary.max_velocity_ms.toFixed(1)} m/s` },
    {
      label: "Apogee",
      value: summary.time_to_apogee_s
        ? `${summary.time_to_apogee_s.toFixed(1)} s`
        : "—",
    },
    { label: "Flight Time", value: `${summary.flight_time_s.toFixed(1)} s` },
    {
      label: "Stability",
      value:
        summary.min_stability_cal != null && summary.max_stability_cal != null
          ? `${summary.min_stability_cal.toFixed(2)} – ${summary.max_stability_cal.toFixed(2)} cal`
          : "—",
    },
  ];

  return (
    <Card>
      <CardContent className="flex flex-wrap gap-3 py-3">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-1.5">
            <Badge variant="neutral" className="text-[10px] px-1.5 py-0">
              {item.label}
            </Badge>
            <span className="text-sm font-heading">{item.value}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function SimCharts({ sim }: { sim: FlightData }) {
  const time = sim.timeseries.TYPE_TIME;
  if (!time) return null;

  const apogee = sim.events.APOGEE?.[0];
  const burnout = sim.events.BURNOUT?.[0];

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {CHARTS.map((chart) => {
        const yData = sim.timeseries[chart.yKey];
        if (!yData) return null;

        const data = time.map((t, i) => ({
          time: parseFloat(t.toFixed(3)),
          value: parseFloat(yData[i]?.toFixed(4) ?? "0"),
        }));

        const chartConfig: ChartConfig = {
          value: { label: chart.title, color: "var(--chart-1)" },
        };

        return (
          <Card key={chart.id}>
            <CardHeader className="py-3">
              <CardTitle className="text-xs">{chart.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <ChartContainer config={chartConfig} className="h-[200px] w-full">
                <LineChart data={data}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--border)"
                    opacity={0.3}
                  />
                  <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <ChartTooltip content={<ChartTooltipContent />} />
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
                    />
                  )}
                  {apogee != null && (
                    <ReferenceLine
                      x={parseFloat(apogee.toFixed(3))}
                      stroke="var(--chart-4)"
                      strokeDasharray="4 4"
                    />
                  )}
                </LineChart>
              </ChartContainer>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

import { ScrollText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import type { WatchEvent } from "@/hooks/useWatchSocket";

export interface LogEntry {
  timestamp: string;
  level: "info" | "warn" | "error" | "success";
  source: string;
  message: string;
  detail?: string;
}

const TYPE_LABELS: Record<string, { label: string; verb: string }> = {
  cadsmith: { label: "cadsmith", verb: "Writing script" },
  step: { label: "step", verb: "Generating" },
  stl: { label: "stl", verb: "Exporting" },
  parts: { label: "part", verb: "Extracting" },
  openrocket: { label: "openrocket", verb: "Updating design" },
  flight: { label: "flight", verb: "Running flight" },
  assembly: { label: "assembly", verb: "Building assembly" },
  report: { label: "report", verb: "Reporting" },
  manifest: { label: "manifest", verb: "Building manifest" },
  gcode: { label: "gcode", verb: "Slicing" },
  script: { label: "script", verb: "Running script" },
  unknown: { label: "file", verb: "Processing" },
};

export function eventsToLogs(events: WatchEvent[]): LogEntry[] {
  return events.map((e) => {
    const meta = TYPE_LABELS[e.type] ?? TYPE_LABELS.unknown;
    const filename = e.relative_path?.split("/").pop() ?? "";
    return {
      timestamp: e.timestamp,
      level: "info" as const,
      source: meta.label,
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

export function SessionLogCard({ logs }: { logs: LogEntry[] }) {
  if (logs.length === 0) return null;

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="shrink-0">
        <CardTitle className="flex items-center gap-2 text-sm"><ScrollText className="size-4" /> Session Log</CardTitle>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-y-auto">
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
      </CardContent>
    </Card>
  );
}

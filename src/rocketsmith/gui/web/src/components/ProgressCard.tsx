import { memo, useCallback, useEffect, useState } from "react";
import { fetchJson } from "@/lib/server";
import { Hammer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useFileTree } from "@/hooks/useFileTree";
import type { FileNode } from "@/hooks/useFileTree";

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
        node.path.startsWith("gui/progress/") &&
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

export function useProgressData(treeVersion: number) {
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

export const ProgressCard = memo(function ProgressCard({ parts }: { parts: PartProgress[] }) {
  if (parts.length === 0) return null;

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="shrink-0">
        <CardTitle className="flex items-center gap-2 text-sm"><Hammer className="size-4" /> Build Progress</CardTitle>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-y-auto space-y-3">
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
                    {info.status === "failed" ? "\u2717 " : info.status === "done" ? "\u2713 " : ""}{name}
                  </Badge>
                ))}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
});

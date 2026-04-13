import { useEffect, useState } from "react";
import { fetchText } from "@/lib/server";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface DiffLine {
  type: "added" | "removed" | "unchanged";
  content: string;
  lineNo: number | null;
}

function computeDiff(oldText: string | null, newText: string): DiffLine[] {
  const newLines = newText.split("\n");
  if (oldText === null) {
    return newLines.map((line, i) => ({
      type: "added",
      content: line,
      lineNo: i + 1,
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

interface CodeViewerCardProps {
  /** Relative path to a file (e.g. "cadsmith/source/nose_cone.py"). */
  file: string;
  /** Optional title override. Defaults to the filename. */
  title?: string;
  /** Hide the title header entirely. */
  hideTitle?: boolean;
  /** Optional previous content for diff highlighting. */
  previousContent?: string | null;
  /** CSS class for the card. */
  className?: string;
}

export function CodeViewerCard({
  file,
  title,
  hideTitle = false,
  previousContent = null,
  className,
}: CodeViewerCardProps) {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchText(file)
      .then((text) => {
        setContent(text);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [file]);

  const filename = file.split("/").pop() ?? file;
  const displayTitle = title ?? filename;

  if (loading) {
    return (
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-xs">{displayTitle}</CardTitle>
        </CardHeader>
        <CardContent className="flex h-32 items-center justify-center">
          <p className="text-sm text-foreground/40">Loading...</p>
        </CardContent>
      </Card>
    );
  }

  if (content === null) {
    return (
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-xs">{displayTitle}</CardTitle>
        </CardHeader>
        <CardContent className="flex h-32 items-center justify-center">
          <p className="text-sm text-foreground/40">File not found</p>
        </CardContent>
      </Card>
    );
  }

  const lines = computeDiff(previousContent, content);
  const showDiff = previousContent !== null;

  return (
    <Card className={className ?? "py-0 gap-0 h-[500px] flex flex-col"}>
      {!hideTitle && (
        <CardHeader className="py-3 shrink-0">
          <CardTitle className="text-xs">{displayTitle}</CardTitle>
        </CardHeader>
      )}
      <CardContent className="p-0 flex-1 min-h-0">
        <div className="h-full overflow-auto rounded-b-base bg-secondary-background px-3 py-2">
          <pre className="text-xs leading-relaxed min-w-full w-max">
            {lines.map((line, i) => (
              <div
                key={i}
                className={`hover:bg-foreground/5 ${
                  showDiff && line.type === "added"
                    ? "bg-green-500/10 text-green-700 dark:text-green-400"
                    : showDiff && line.type === "removed"
                      ? "bg-red-500/10 text-red-700 dark:text-red-400"
                      : "text-foreground/70"
                }`}
              >
                <span className="mr-2 inline-block w-8 text-right text-foreground/30 select-none">
                  {line.lineNo ?? ""}
                </span>
                {showDiff && (
                  <span className="mr-2 inline-block w-4 text-center select-none">
                    {line.type === "added"
                      ? "+"
                      : line.type === "removed"
                        ? "\u2212"
                        : " "}
                  </span>
                )}
                {line.content}
              </div>
            ))}
          </pre>
        </div>
      </CardContent>
    </Card>
  );
}

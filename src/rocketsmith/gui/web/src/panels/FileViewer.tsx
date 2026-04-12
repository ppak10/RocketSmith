import { useEffect, useState } from "react";
import { apiBase } from "@/lib/server";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";

interface FileViewerProps {
  file: string;
}

export function FileViewer({ file }: FileViewerProps) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setContent(null);
    setError(false);

    fetch(`${apiBase()}/api/files/${file}`)
      .then((r) => (r.ok ? r.text() : Promise.reject()))
      .then(setContent)
      .catch(() => setError(true));
  }, [file]);

  const filename = file.split("/").pop() ?? file;

  return (
    <Card className="flex flex-col m-4">
      <CardHeader>
        <CardTitle className="text-sm">{filename}</CardTitle>
        <p className="text-xs text-foreground/50">{file}</p>
      </CardHeader>
      <CardContent className="flex-1 overflow-auto">
        {error ? (
          <p className="text-sm text-foreground/40">Failed to load file</p>
        ) : content === null ? (
          <p className="text-sm text-foreground/40">Loading...</p>
        ) : (
          <pre className="text-xs leading-relaxed">
            {content.split("\n").map((line, i) => (
              <div key={i} className="text-foreground/70">
                <span className="mr-3 inline-block w-8 text-right text-foreground/30 select-none">
                  {i + 1}
                </span>
                {line}
              </div>
            ))}
          </pre>
        )}
      </CardContent>
    </Card>
  );
}

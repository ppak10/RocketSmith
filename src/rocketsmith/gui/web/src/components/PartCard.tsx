import { memo, useState, useEffect } from "react";
import { Box } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Part3DViewerCard } from "@/components/PartPreviewCard";
import { CodeViewerCard } from "@/components/CodeViewerCard";

export interface PartProgressOutputs {
  [output: string]: { status: string; path: string | null };
}

interface PartCardProps {
  /** Part name (stem, no extension). */
  partName: string;
  /** Override the source file path. Defaults to "cadsmith/source/{partName}.py". */
  sourcePath?: string;
  /** Override the STL file path. Defaults to "gui/assets/stl/{partName}.stl". */
  stlPath?: string;
  /** Override the GCode file path. Defaults to "prusaslicer/gcode/{partName}.gcode". */
  gcodePath?: string;
  /** Auto-rotate the 3D model. Default false. */
  autoRotate?: boolean;
  /** Show the 3D display mode toggle. Default true. */
  showModeToggle?: boolean;
  /** Use simple OrbitControls. Default false. */
  simpleControls?: boolean;
  /** Disable camera controls (static auto-rotating preview). Default false. */
  staticPreview?: boolean;
  /** Default active tab. Auto-switches to "model" when STL becomes available. */
  defaultTab?: "source" | "model" | "gcode";
  /** Previous source content for diff highlighting. */
  previousSourceContent?: string | null;
  /** Preview generation progress outputs. Shown as badges when generating. */
  progress?: PartProgressOutputs | null;
  /** Bumped when the STL file is updated, to refresh the 3D viewer. */
  stlVersion?: number;
  /** Set of completed format directory prefixes (e.g. "cadsmith/source", "cadsmith/step"). */
  completedFormats?: Set<string>;
  /** CSS class for the outer card. */
  className?: string;
}

export const PartCard = memo(function PartCard({
  partName,
  sourcePath,
  stlPath,
  gcodePath,
  autoRotate = false,
  showModeToggle = true,
  simpleControls = false,
  staticPreview = false,
  defaultTab = "model",
  previousSourceContent = null,
  progress = null,
  stlVersion = 0,
  completedFormats,
  className = "h-[500px]",
}: PartCardProps) {
  const resolvedSource = sourcePath ?? `cadsmith/source/${partName}.py`;
  const resolvedGcode = gcodePath ?? `prusaslicer/gcode/${partName}.gcode`;
  const [activeTab, setActiveTab] = useState(defaultTab);

  // Auto-switch to model tab when STL becomes available.
  useEffect(() => {
    if (defaultTab === "model" && activeTab === "source") {
      setActiveTab("model");
    }
  }, [defaultTab]);

  // Switch to source tab when a new diff arrives (cadsmith update).
  useEffect(() => {
    if (previousSourceContent != null) {
      setActiveTab("source");
    }
  }, [previousSourceContent]);

  // Pipeline stages in order. Each maps a format dir prefix to a label.
  const PIPELINE_STAGES = [
    { key: "cadsmith/source", label: "source" },
    { key: "cadsmith/step", label: "step" },
    { key: "gui/assets/stl", label: "stl" },
    { key: "prusaslicer/gcode", label: "gcode" },
  ];

  // Determine per-stage status from completedFormats.
  const stageStatuses = PIPELINE_STAGES.map(({ key, label }) => {
    const done = completedFormats?.has(key) ?? false;
    return { label, done };
  });

  // The "in progress" stage is the first not-done after the last done.
  const lastDoneIdx = stageStatuses.reduce(
    (acc, s, i) => (s.done ? i : acc),
    -1,
  );
  const inProgressIdx = lastDoneIdx + 1 < stageStatuses.length ? lastDoneIdx + 1 : -1;

  return (
    <Card className={`${className} flex flex-col overflow-hidden pb-0 gap-0`}>
      <CardHeader className="shrink-0 pb-0 space-y-1.5">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Box className="size-4" /> {partName.replace(/_/g, " ")}
        </CardTitle>
        {completedFormats && completedFormats.size > 0 && (
          <div className="flex flex-wrap gap-1">
            {stageStatuses.map(({ label, done }, i) => (
              <Badge
                key={label}
                variant={done ? "default" : "neutral"}
                className={`text-[9px] px-1.5 py-0 ${
                  i === inProgressIdx ? "animate-pulse" : ""
                }`}
              >
                {done ? "\u2713 " : i === inProgressIdx ? "\u25CB " : ""}{label}
              </Badge>
            ))}
          </div>
        )}
      </CardHeader>
      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as "source" | "model" | "gcode")}
        className="flex min-h-0 flex-1 flex-col"
      >
        <TabsList className="shrink-0 mx-3 mt-2 w-fit">
          <TabsTrigger value="source">Source</TabsTrigger>
          <TabsTrigger value="model">Model</TabsTrigger>
          <TabsTrigger value="gcode">GCode</TabsTrigger>
        </TabsList>

        <TabsContent value="source" className="flex-1 min-h-0 m-0 mt-2 overflow-hidden">
          <CodeViewerCard
            file={resolvedSource}
            hideTitle
            previousContent={previousSourceContent}
            className="h-full border-0 shadow-none flex flex-col py-0 gap-0"
          />
        </TabsContent>

        <TabsContent value="model" className="flex-1 min-h-0 m-0 mt-2 overflow-hidden">
          {activeTab === "model" && (
            <Part3DViewerCard
              key={stlVersion}
              partName={partName}
              stlPath={stlPath}
              autoRotate={autoRotate}
              showModeToggle={showModeToggle}
              simpleControls={simpleControls}
              staticPreview={staticPreview}
              className="h-full border-0 shadow-none"
            />
          )}
        </TabsContent>

        <TabsContent value="gcode" className="flex-1 min-h-0 m-0 mt-2 overflow-hidden">
          <CodeViewerCard
            file={resolvedGcode}
            hideTitle
            className="h-full border-0 shadow-none flex flex-col py-0 gap-0"
          />
        </TabsContent>
      </Tabs>
    </Card>
  );
});

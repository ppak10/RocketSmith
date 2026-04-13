import { Box } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Part3DViewerCard } from "@/components/PartPreviewCard";
import { CodeViewerCard } from "@/components/CodeViewerCard";

interface PartCardProps {
  /** Part name (stem, no extension). */
  partName: string;
  /** Override the source file path. Defaults to "cadsmith/source/{partName}.py". */
  sourcePath?: string;
  /** Override the STL file path. Defaults to "cadsmith/stl/{partName}.stl". */
  stlPath?: string;
  /** Auto-rotate the 3D model. Default false. */
  autoRotate?: boolean;
  /** Show the 3D display mode toggle. Default true. */
  showModeToggle?: boolean;
  /** Use simple OrbitControls. Default false. */
  simpleControls?: boolean;
  /** Default active tab. */
  defaultTab?: "source" | "model";
  /** Previous source content for diff highlighting. */
  previousSourceContent?: string | null;
  /** CSS class for the outer card. */
  className?: string;
}

export function PartCard({
  partName,
  sourcePath,
  stlPath,
  autoRotate = false,
  showModeToggle = true,
  simpleControls = false,
  defaultTab = "model",
  previousSourceContent = null,
  className = "h-[500px]",
}: PartCardProps) {
  const resolvedSource = sourcePath ?? `cadsmith/source/${partName}.py`;

  return (
    <Card className={`${className} flex flex-col gap-0 py-0`}>
      <CardHeader className="shrink-0 pb-0">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Box className="size-4" /> {partName.replace(/_/g, " ")}
        </CardTitle>
      </CardHeader>
      <Tabs defaultValue={defaultTab} className="flex h-full flex-col">
        <TabsList className="shrink-0 mx-3 mt-2 w-fit">
          <TabsTrigger value="model">Model</TabsTrigger>
          <TabsTrigger value="source">Source</TabsTrigger>
        </TabsList>

        <TabsContent value="model" className="flex-1 min-h-0 m-0">
          <Part3DViewerCard
            partName={partName}
            stlPath={stlPath}
            autoRotate={autoRotate}
            showModeToggle={showModeToggle}
            simpleControls={simpleControls}
            className="h-full border-0 shadow-none"
          />
        </TabsContent>

        <TabsContent value="source" className="flex-1 min-h-0 m-0">
          <CodeViewerCard
            file={resolvedSource}
            hideTitle
            previousContent={previousSourceContent}
            className="h-full border-0 shadow-none"
          />
        </TabsContent>
      </Tabs>
    </Card>
  );
}

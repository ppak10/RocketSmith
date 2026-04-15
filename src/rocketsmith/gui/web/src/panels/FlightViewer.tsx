import { FlightCard } from "@/components/FlightCard";

interface FlightViewerProps {
  treeVersion: number;
}

export function FlightViewer({ treeVersion }: FlightViewerProps) {
  return (
    <div className="p-4 h-full">
      <FlightCard treeVersion={treeVersion} className="h-full" />
    </div>
  );
}

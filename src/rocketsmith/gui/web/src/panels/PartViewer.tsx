import { useEffect, useState } from "react";
import { fetchJson } from "@/lib/server";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { PartCard } from "@/components/PartCard";
import { usePartValidation } from "@/hooks/usePartValidation";

type Qty = [number, string];

interface UnitVec {
  x: Qty;
  y: Qty;
  z: Qty;
}

interface PartData {
  name: string;
  display_name: string | null;
  stl_path: string | null;
  step_path: string | null;
  brep_path: string | null;
  bounding_box: UnitVec | null;
  color: string;
  cost: number | null;
  description: string | null;
  id: string | null;
  volume: Qty | null;
  surface_area: Qty | null;
  center_of_mass: UnitVec | null;
  mass: Qty | null;
}

function fmtQty(q: Qty | null, precision = 1): string {
  if (!q) return "\u2014";
  const [val, unit] = q;
  const short = unit
    .replace("millimeter ** 3", "mm\u00B3")
    .replace("millimeter ** 2", "mm\u00B2")
    .replace("millimeter", "mm")
    .replace("gram", "g")
    .replace("kilogram", "kg");
  return `${val.toFixed(precision)} ${short}`;
}

function fmtVec(v: UnitVec | null): string {
  if (!v) return "\u2014";
  return `${v.x[0].toFixed(1)} \u00D7 ${v.y[0].toFixed(1)} \u00D7 ${v.z[0].toFixed(1)} mm`;
}

// Stat row

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <Badge variant="neutral" className="text-[10px] px-1.5 py-0">
        {label}
      </Badge>
      <span className="text-sm font-heading">{value}</span>
    </div>
  );
}

// Main component

interface PartViewerProps {
  file: string;
}

export function PartViewer({ file }: PartViewerProps) {
  const [part, setPart] = useState<PartData | null>(null);
  const [loading, setLoading] = useState(true);
  const { deviations } = usePartValidation();

  useEffect(() => {
    setLoading(true);
    fetchJson<PartData>(file)
      .then((data) => {
        setPart(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [file]);

  if (loading) {
    return (
      <Card className="h-full">
        <CardContent className="flex h-full items-center justify-center">
          <p className="text-sm text-foreground/40">Loading part...</p>
        </CardContent>
      </Card>
    );
  }

  if (!part) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="text-sm">Part</CardTitle>
        </CardHeader>
        <CardContent className="flex h-48 items-center justify-center">
          <p className="text-sm text-foreground/40">Part data not found.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Name */}
      <h2 className="text-lg font-heading">{part.display_name ?? part.name}</h2>

      {/* Deviation warning */}
      {deviations
        .filter((d) => d.partName === part.name)
        .map((d) => (
          <Alert key={d.field}>
            <AlertTitle>Part out of date</AlertTitle>
            <AlertDescription>
              {d.displayName} {d.field}: expected {d.expected.toFixed(1)} mm from component tree, but CAD is {d.actual.toFixed(1)} mm ({d.diff.toFixed(1)} mm deviation). Regenerate this part to match the current design.
            </AlertDescription>
          </Alert>
        ))}

      {/* Summary badges */}
      <div className="flex flex-wrap gap-3">
        {part.mass && <Stat label="Mass" value={fmtQty(part.mass)} />}
        {part.volume && <Stat label="Volume" value={fmtQty(part.volume, 0)} />}
        {part.surface_area && <Stat label="Surface Area" value={fmtQty(part.surface_area, 0)} />}
        {part.bounding_box && <Stat label="Bounding Box" value={fmtVec(part.bounding_box)} />}
        {part.cost != null && <Stat label="Cost" value={`$${part.cost.toFixed(2)}`} />}
      </div>

      {/* Tabbed part viewer — Model / Source */}
      <PartCard partName={part.name} />

    </div>
  );
}

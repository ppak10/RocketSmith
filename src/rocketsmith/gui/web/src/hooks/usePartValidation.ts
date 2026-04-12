import { useEffect, useState } from "react";
import { apiBase } from "@/lib/server";

export interface PartDeviation {
  partName: string;
  displayName: string;
  field: string;
  expected: number;
  actual: number;
  diff: number;
}

interface ComponentTreeData {
  stages: {
    components: ComponentData[];
  }[];
}

interface ComponentData {
  name: string;
  type: string;
  dimensions: Record<string, unknown>;
  agent: {
    fate: string;
    dfam_shoulder_length_mm?: number | null;
  } | null;
  step_path: string | null;
  children: ComponentData[];
}

type Qty = [number, string];

function qtyVal(v: unknown): number {
  if (Array.isArray(v)) return v[0] as number;
  if (typeof v === "number") return v;
  return 0;
}

const THRESHOLD_MM = 1.0;

/**
 * Compare component tree dimensions against part JSON bounding boxes.
 * Returns deviations > 1mm threshold.
 */
export function usePartValidation() {
  const [deviations, setDeviations] = useState<PartDeviation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        // Fetch component tree.
        const treeRes = await fetch(`${apiBase()}/api/files/component_tree.json`);
        if (!treeRes.ok) { setLoading(false); return; }
        const tree: ComponentTreeData = await treeRes.json();

        // Collect printed components with step paths.
        const printed: ComponentData[] = [];
        const walk = (nodes: ComponentData[]) => {
          for (const n of nodes) {
            if (n.agent?.fate === "print" && n.step_path) printed.push(n);
            walk(n.children);
          }
        };
        for (const stage of tree.stages) walk(stage.components);

        // Compare each against its part JSON.
        const devs: PartDeviation[] = [];

        for (const comp of printed) {
          const stem = comp.name.toLowerCase().replace(/\s+/g, "_");
          const partRes = await fetch(`${apiBase()}/api/files/parts/${stem}.json`);
          if (!partRes.ok) continue;
          const part = await partRes.json();

          if (!part.bounding_box) continue;

          const bboxZ = qtyVal(part.bounding_box.z);
          const bboxX = qtyVal(part.bounding_box.x);

          const dims = comp.dimensions;
          const kind = dims.kind as string | undefined;

          // Expected height along Z.
          let expectedZ = 0;
          if (kind === "nose_cone") {
            expectedZ = qtyVal(dims.length) + (comp.agent?.dfam_shoulder_length_mm ?? 0);
          } else if (kind === "tube") {
            expectedZ = qtyVal(dims.length);
          }

          // Expected width (OD or base_od).
          let expectedWidth = 0;
          if (kind === "nose_cone") {
            expectedWidth = qtyVal(dims.base_od);
          } else if (kind === "tube") {
            expectedWidth = qtyVal(dims.od);
          }

          if (expectedZ > 0) {
            const diff = Math.abs(bboxZ - expectedZ);
            if (diff > THRESHOLD_MM) {
              devs.push({
                partName: stem,
                displayName: part.display_name ?? comp.name,
                field: "length (Z)",
                expected: expectedZ,
                actual: bboxZ,
                diff,
              });
            }
          }

          // For width, only check if no fins (fins extend the bbox beyond OD).
          const hasFins = comp.children.some((c) => c.type.includes("FinSet"));
          if (expectedWidth > 0 && !hasFins) {
            const diff = Math.abs(bboxX - expectedWidth);
            if (diff > THRESHOLD_MM) {
              devs.push({
                partName: stem,
                displayName: part.display_name ?? comp.name,
                field: "width (X)",
                expected: expectedWidth,
                actual: bboxX,
                diff,
              });
            }
          }
        }

        setDeviations(devs);
      } catch {}
      setLoading(false);
    })();
  }, []);

  return { deviations, loading };
}

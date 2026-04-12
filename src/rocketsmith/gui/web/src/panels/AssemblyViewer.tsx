import { useEffect, useState, Suspense, useMemo } from "react";
import { apiBase } from "@/lib/server";
import { Canvas, useLoader } from "@react-three/fiber";
import { TrackballControls, Environment, Center, Edges, GizmoHelper, GizmoViewport } from "@react-three/drei";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import * as THREE from "three";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Eye, EyeOff } from "lucide-react";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Box, Grid3x3, Sparkles, Scissors } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { CanvasErrorBoundary } from "@/components/CanvasErrorBoundary";
import { usePartValidation } from "@/hooks/usePartValidation";

type Qty = [number, string];

interface Vec3 {
  x: Qty;
  y: Qty;
  z: Qty;
}

function mag(q: Qty): number {
  return q[0];
}

// ── Assembly JSON types ────────────────────────────────────────────────────

interface AssemblyPartRef {
  part_file: string;
  position: Vec3;
  rotation: Vec3;
  color: string;
  invert_z: boolean;
  joint_offset: Qty | null;
}

interface AssemblyData {
  schema_version: number;
  project_root: string | null;
  generated_at: string;
  parts: AssemblyPartRef[];
  total_length: Qty;
}

// ── Resolved part (assembly ref + part JSON merged) ────────────────────────

interface PartData {
  name: string;
  display_name: string | null;
  stl_path: string | null;
  step_path: string | null;
  bounding_box: Vec3 | null;
  mass: Qty | null;
}

interface ResolvedPart {
  ref: AssemblyPartRef;
  data: PartData | null;
  stlUrl: string | null;
}

// ── Display modes ──────────────────────────────────────────────────────────

type DisplayMode = "shaded" | "wireframe" | "rendered";

const MODES: { value: DisplayMode; label: string; icon: typeof Box }[] = [
  { value: "shaded", label: "Shaded", icon: Box },
  { value: "wireframe", label: "Wireframe", icon: Grid3x3 },
  { value: "rendered", label: "Rendered", icon: Sparkles },
];

// ── Main component ─────────────────────────────────────────────────────────

export function AssemblyViewer() {
  const [assembly, setAssembly] = useState<AssemblyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [resolved, setResolved] = useState<ResolvedPart[]>([]);
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [mode, setMode] = useState<DisplayMode>("shaded");
  const [crossSection, setCrossSection] = useState(false);
  const { deviations } = usePartValidation();
  const [clipPosition, setClipPosition] = useState(100);

  // Load assembly.json.
  useEffect(() => {
    setLoading(true);
    fetch(`${apiBase()}/api/files/assembly.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: AssemblyData | null) => {
        setAssembly(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Resolve part refs → fetch each part JSON + probe STL.
  useEffect(() => {
    if (!assembly) return;

    Promise.all(
      assembly.parts.map(async (ref) => {
        // Fetch part JSON.
        let data: PartData | null = null;
        try {
          const r = await fetch(`${apiBase()}/api/files/${ref.part_file}`);
          if (r.ok) data = await r.json();
        } catch {}

        // Derive STL URL from part data or part_file stem.
        const stem = ref.part_file.replace(/^parts\//, "").replace(/\.json$/, "");
        const stlPath = data?.stl_path
          ? data.stl_path
          : `stl/${stem}.stl`;
        const stlUrl = `${apiBase()}/api/files/${stlPath}`;

        // Probe if STL exists.
        let stlAvailable = false;
        try {
          const r = await fetch(stlUrl, { method: "HEAD" });
          stlAvailable = r.ok;
        } catch {}

        return {
          ref,
          data,
          stlUrl: stlAvailable ? stlUrl : null,
        } as ResolvedPart;
      }),
    ).then((parts) => {
      setResolved(parts);
      setVisible(
        Object.fromEntries(parts.map((p) => [p.ref.part_file, true])),
      );
    });
  }, [assembly]);


  const togglePart = (key: string) =>
    setVisible((prev) => ({ ...prev, [key]: !prev[key] }));

  if (loading) {
    return (
      <Card className="h-full">
        <CardContent className="flex h-full items-center justify-center">
          <p className="text-sm text-foreground/40">Loading assembly...</p>
        </CardContent>
      </Card>
    );
  }

  if (!assembly || assembly.parts.length === 0) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="text-sm">Assembly</CardTitle>
        </CardHeader>
        <CardContent className="flex h-48 items-center justify-center">
          <p className="text-sm text-foreground/40">
            No assembly data found. Run cadsmith_assembly(action="generate") to
            create it.
          </p>
        </CardContent>
      </Card>
    );
  }

  const renderableParts = resolved.filter((p) => p.stlUrl);

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Summary */}
      <div className="flex flex-wrap gap-3">
        <div className="flex items-center gap-1.5">
          <Badge variant="neutral" className="text-[10px] px-1.5 py-0">
            Parts
          </Badge>
          <span className="text-sm font-heading">{renderableParts.length}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Badge variant="neutral" className="text-[10px] px-1.5 py-0">
            Length
          </Badge>
          <span className="text-sm font-heading">
            {mag(assembly.total_length).toFixed(0)} mm
          </span>
        </div>
      </div>

      {/* Deviation warnings */}
      {deviations.length > 0 && (
        <Alert>
          <AlertTitle>Parts out of date</AlertTitle>
          <AlertDescription>
            {deviations.map((d) => (
              <div key={`${d.partName}-${d.field}`}>
                {d.displayName} {d.field}: expected {d.expected.toFixed(1)} mm, CAD is {d.actual.toFixed(1)} mm ({d.diff.toFixed(1)} mm off)
              </div>
            ))}
            <p className="mt-1 text-xs">Regenerate parts to match the current component tree.</p>
          </AlertDescription>
        </Alert>
      )}

      {/* 3D View */}
      <Card className="h-[500px] flex flex-col py-0 gap-0 relative">
        <div className="absolute top-3 left-3 z-10">
          <RadioGroup
            value={mode}
            onValueChange={(v: string) => setMode(v as DisplayMode)}
            className="flex gap-3 rounded-base border-2 border-border bg-background px-2 py-1.5"
          >
            {MODES.map((m) => (
              <label
                key={m.value}
                className="flex items-center gap-1.5 cursor-pointer text-xs font-heading"
              >
                <RadioGroupItem value={m.value} />
                <m.icon className="size-3.5" />
                {m.label}
              </label>
            ))}
          </RadioGroup>
        </div>

        {/* Cross-section controls */}
        <div className="absolute top-3 right-3 z-10 flex items-center gap-2">
          <div
            className={`flex items-center gap-2 rounded-base border-2 bg-background px-2 py-1.5 cursor-pointer ${crossSection ? "border-main" : "border-border"}`}
            onClick={() => setCrossSection((v) => !v)}
          >
            <Scissors className="size-3.5" />
            <span className="text-xs font-heading">Section</span>
          </div>
          {crossSection && (
            <div className="flex items-center gap-2 rounded-base border-2 border-border bg-background px-2 py-1.5 w-40">
              <Slider
                value={[clipPosition]}
                onValueChange={([v]) => setClipPosition(v)}
                min={0}
                max={100}
                step={1}
              />
            </div>
          )}
        </div>

        <CardContent className="h-full p-0 overflow-hidden rounded-base">
          <CanvasErrorBoundary>
            <Canvas
              camera={{ position: [0, -600, 0], fov: 45, near: 1, far: 5000, up: [-1, 0, 0] }}
              gl={{ localClippingEnabled: true }}
            >
              <Environment preset="studio" />
              <Suspense fallback={null}>
                <AssemblyScene
                  parts={renderableParts}
                  visible={visible}
                  mode={mode}
                  clipZ={crossSection ? (clipPosition / 100) * 200 : null}
                />
              </Suspense>
              <TrackballControls noZoom={false} noPan={false} noRotate={false} dynamicDampingFactor={0.1} />
              <GizmoHelper alignment="bottom-left" margin={[60, 60]}>
                <GizmoViewport labelColor="white" axisHeadScale={0.8} />
              </GizmoHelper>
            </Canvas>
          </CanvasErrorBoundary>
        </CardContent>
      </Card>

      {/* Parts legend */}
      <Card className="pt-0 gap-0">
        <CardHeader className="py-3">
          <CardTitle className="text-xs">Parts</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-1.5">
            {resolved.map((rp) => {
              const hasStl = !!rp.stlUrl;
              const isVisible = visible[rp.ref.part_file] ?? true;
              const label = rp.data?.display_name ?? rp.data?.name ?? rp.ref.part_file.replace(/^parts\//, "").replace(/\.json$/, "");
              return (
                <li key={rp.ref.part_file} className="flex items-center gap-2 text-sm">
                  <button
                    onClick={() => togglePart(rp.ref.part_file)}
                    disabled={!hasStl}
                    className="shrink-0 disabled:opacity-30"
                  >
                    {isVisible && hasStl ? (
                      <Eye className="size-4" />
                    ) : (
                      <EyeOff className="size-4 text-foreground/30" />
                    )}
                  </button>
                  <Badge
                    variant="neutral"
                    className="text-[10px] px-1.5 py-0 text-white"
                    style={{ backgroundColor: hasStl ? rp.ref.color : undefined }}
                  >
                    {label}
                  </Badge>
                  {rp.data?.bounding_box && (
                    <span className="ml-auto text-xs text-foreground/40">
                      {mag(rp.data.bounding_box.z).toFixed(0)} mm
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Assembly 3D scene ──────────────────────────────────────────────────────

function AssemblyScene({
  parts,
  visible,
  mode,
  clipZ,
}: {
  parts: ResolvedPart[];
  visible: Record<string, boolean>;
  mode: DisplayMode;
  clipZ: number | null;
}) {
  const clippingPlanes = useMemo(() => {
    if (clipZ === null) return [];
    return [new THREE.Plane(new THREE.Vector3(0, 1, 0), clipZ)];
  }, [clipZ]);

  return (
    <Center>
      <group>
        {parts.map((rp) =>
          visible[rp.ref.part_file] !== false && rp.stlUrl ? (
            <AssemblyPartMesh
              key={rp.ref.part_file}
              stlUrl={rp.stlUrl}
              position={rp.ref.position}
              rotation={rp.ref.rotation}
              invertZ={rp.ref.invert_z}
              color={rp.ref.color}
              mode={mode}
              clippingPlanes={clippingPlanes}
            />
          ) : null,
        )}
      </group>
    </Center>
  );
}

function AssemblyPartMesh({
  stlUrl,
  position,
  rotation,
  invertZ,
  color,
  mode,
  clippingPlanes,
}: {
  stlUrl: string;
  position: Vec3;
  rotation: Vec3;
  invertZ: boolean;
  color: string;
  mode: DisplayMode;
  clippingPlanes: THREE.Plane[];
}) {
  const geometry = useLoader(STLLoader, stlUrl);

  const prepared = useMemo(() => {
    const geo = geometry.clone();
    geo.computeVertexNormals();
    return geo;
  }, [geometry]);

  const px = mag(position.x);
  const py = mag(position.y);
  const pz = mag(position.z);
  const rx = (mag(rotation.x) * Math.PI) / 180 + (invertZ ? Math.PI : 0);
  const ry = (mag(rotation.y) * Math.PI) / 180;
  const rz = (mag(rotation.z) * Math.PI) / 180;

  return (
    <mesh
      geometry={prepared}
      position={[px, py, pz]}
      rotation={[rx, ry, rz]}
    >
      {mode === "wireframe" ? (
        <meshBasicMaterial color={color} wireframe side={THREE.DoubleSide} clippingPlanes={clippingPlanes} />
      ) : mode === "rendered" ? (
        <meshPhysicalMaterial
          color={color}
          metalness={0.3}
          roughness={0.4}
          clearcoat={0.3}
          clearcoatRoughness={0.2}
          side={THREE.DoubleSide}
          clippingPlanes={clippingPlanes}
        />
      ) : (
        <>
          <meshStandardMaterial
            color={color}
            metalness={0.1}
            roughness={0.6}
            side={THREE.DoubleSide}
            clippingPlanes={clippingPlanes}
          />
          <Edges threshold={15} color="#444444" />
        </>
      )}
    </mesh>
  );
}

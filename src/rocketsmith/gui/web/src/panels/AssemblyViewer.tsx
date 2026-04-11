import { useEffect, useState, Suspense, useRef, useMemo } from "react";
import { apiBase } from "@/lib/server";
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { OrbitControls, Environment, Center } from "@react-three/drei";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import * as THREE from "three";
import type { Group } from "three";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

/** A pintdantic quantity: [magnitude, unit_string] */
type Qty = [number, string];

/** A pintdantic Vec3: { x: Qty, y: Qty, z: Qty } */
interface Vec3 {
  x: Qty;
  y: Qty;
  z: Qty;
}

/** Extract the magnitude from a pintdantic quantity. */
function mag(q: Qty): number {
  return q[0];
}

interface AssemblyPart {
  name: string;
  stl_path: string | null;
  step_path: string | null;
  bounding_box: Vec3 | null;
  color: string;
  cost: number | null;
  description: string | null;
  id: string | null;
  position: Vec3;
  rotation: Vec3;
}

interface AssemblyData {
  schema_version: number;
  project_root: string | null;
  generated_at: string;
  parts: AssemblyPart[];
  total_length: Qty;
}

const PART_COLORS = [
  "#8ecae6",
  "#219ebc",
  "#ffb703",
  "#fb8500",
  "#a8dadc",
  "#457b9d",
  "#e76f51",
  "#2a9d8f",
];

export function AssemblyViewer() {
  const file = "assembly.json";
  const [assembly, setAssembly] = useState<AssemblyData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${apiBase()}/api/files/${file}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        setAssembly(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [file]);

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

  const printedParts = assembly.parts.filter((p) => p.stl_path);
  const nonGeomParts = assembly.parts.filter((p) => !p.stl_path);

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto">
      {/* Summary */}
      <Card>
        <CardContent className="flex flex-wrap gap-3 py-3">
          <div className="flex items-center gap-1.5">
            <Badge variant="neutral" className="text-[10px] px-1.5 py-0">
              Parts
            </Badge>
            <span className="text-sm font-heading">{printedParts.length}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Badge variant="neutral" className="text-[10px] px-1.5 py-0">
              Length
            </Badge>
            <span className="text-sm font-heading">
              {mag(assembly.total_length).toFixed(0)} mm
            </span>
          </div>
          {nonGeomParts.length > 0 && (
            <div className="flex items-center gap-1.5">
              <Badge variant="neutral" className="text-[10px] px-1.5 py-0">
                Other
              </Badge>
              <span className="text-sm font-heading">
                {nonGeomParts.length}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 3D View */}
      <Card className="flex-1 min-h-[400px]">
        <CardContent className="h-full p-0 overflow-hidden rounded-base">
          <Canvas camera={{ position: [0, 0, 600], fov: 45 }}>
            <ambientLight intensity={0.4} />
            <directionalLight position={[500, 500, 500]} intensity={0.8} />
            <directionalLight position={[-300, 200, -200]} intensity={0.3} />
            <Environment preset="studio" />
            <Suspense fallback={null}>
              <AssemblyScene parts={printedParts} />
            </Suspense>
            <OrbitControls enableDamping dampingFactor={0.1} />
          </Canvas>
        </CardContent>
      </Card>

      {/* Parts legend */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-xs">Parts</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-1.5">
            {assembly.parts.map((part, i) => (
              <li key={part.name} className="flex items-center gap-2 text-sm">
                {part.stl_path ? (
                  <span
                    className="inline-block h-3 w-3 rounded-sm border border-border"
                    style={{
                      backgroundColor:
                        PART_COLORS[i % PART_COLORS.length],
                    }}
                  />
                ) : (
                  <span className="inline-block h-3 w-3 rounded-sm border border-border bg-foreground/10" />
                )}
                <span className="truncate">{part.name}</span>
                {part.bounding_box && (
                  <span className="ml-auto text-xs text-foreground/40">
                    {mag(part.bounding_box.z).toFixed(0)} mm
                  </span>
                )}
                {!part.stl_path && part.description && (
                  <span className="ml-auto text-xs text-foreground/40">
                    {part.description}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

/** Render all parts in the assembly, centered as a group. */
function AssemblyScene({ parts }: { parts: AssemblyPart[] }) {
  const groupRef = useRef<Group>(null);

  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.15;
    }
  });

  return (
    <Center>
      <group ref={groupRef}>
        {parts.map((part, i) => (
          <AssemblyPartMesh
            key={part.name}
            part={part}
            color={PART_COLORS[i % PART_COLORS.length]}
          />
        ))}
      </group>
    </Center>
  );
}

function AssemblyPartMesh({
  part,
  color,
}: {
  part: AssemblyPart;
  color: string;
}) {
  const url = `${apiBase()}/api/files/${part.stl_path}`;
  const geometry = useLoader(STLLoader, url);

  const prepared = useMemo(() => {
    const geo = geometry.clone();
    geo.computeVertexNormals();
    return geo;
  }, [geometry]);

  const rx = mag(part.rotation.x);
  const ry = mag(part.rotation.y);
  const rz = mag(part.rotation.z);
  const px = mag(part.position.x);
  const py = mag(part.position.y);
  const pz = mag(part.position.z);

  return (
    <mesh
      geometry={prepared}
      position={[px, py, pz]}
      rotation={[
        (rx * Math.PI) / 180,
        (ry * Math.PI) / 180,
        (rz * Math.PI) / 180,
      ]}
    >
      <meshStandardMaterial
        color={color}
        metalness={0.1}
        roughness={0.6}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

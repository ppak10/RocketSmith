import { Suspense, useMemo, useState } from "react";
import { CanvasErrorBoundary } from "@/components/CanvasErrorBoundary";
import { fileUrl, hasOfflineFile } from "@/lib/server";
import { Canvas, useLoader } from "@react-three/fiber";
import { TrackballControls, Environment, Center, Edges } from "@react-three/drei";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import * as THREE from "three";
import { Card, CardContent } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Box, Grid3x3, Sparkles } from "lucide-react";

// ── Display modes ──────────────────────────────────────────────────────────

type DisplayMode = "shaded" | "wireframe" | "rendered";

const MODES: { value: DisplayMode; label: string; icon: typeof Box }[] = [
  { value: "shaded", label: "Shaded", icon: Box },
  { value: "wireframe", label: "Wireframe", icon: Grid3x3 },
  { value: "rendered", label: "Rendered", icon: Sparkles },
];

function PartModel({ url, mode }: { url: string; mode: DisplayMode }) {
  const geometry = useLoader(STLLoader, url);

  const centered = useMemo(() => {
    const geo = geometry.clone();
    geo.computeBoundingBox();
    geo.center();
    const box = geo.boundingBox!;
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);
    if (maxDim > 0) geo.scale(3 / maxDim, 3 / maxDim, 3 / maxDim);
    geo.computeVertexNormals();
    return geo;
  }, [geometry]);

  if (mode === "wireframe") {
    return (
      <Center>
        <mesh geometry={centered}>
          <meshBasicMaterial color="#888888" wireframe side={THREE.DoubleSide} />
        </mesh>
      </Center>
    );
  }

  if (mode === "rendered") {
    return (
      <Center>
        <mesh geometry={centered}>
          <meshPhysicalMaterial
            color="#b0b0b0"
            metalness={0.3}
            roughness={0.4}
            clearcoat={0.3}
            clearcoatRoughness={0.2}
            side={THREE.DoubleSide}
          />
        </mesh>
      </Center>
    );
  }

  // shaded with edges
  return (
    <Center>
      <mesh geometry={centered}>
        <meshStandardMaterial
          color="#cccccc"
          metalness={0.1}
          roughness={0.6}
          side={THREE.DoubleSide}
        />
        <Edges threshold={15} color="#666666" />
      </mesh>
    </Center>
  );
}

// ── Part 3D viewer card ────────────────────────────────────────────────────

interface Part3DViewerCardProps {
  partName: string;
}

export function Part3DViewerCard({ partName }: Part3DViewerCardProps) {
  const stlPath = `stl/${partName}.stl`;
  const stlUrl = fileUrl(stlPath);
  const [mode, setMode] = useState<DisplayMode>("shaded");

  if (!hasOfflineFile(stlPath)) {
    return (
      <Card className="h-[500px] flex flex-col items-center justify-center">
        <p className="text-sm text-foreground/40">STL not available</p>
      </Card>
    );
  }

  return (
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

      <CardContent className="h-full p-0 overflow-hidden rounded-base">
        <CanvasErrorBoundary>
          <Canvas camera={{ position: [5, 3, 3], fov: 45, up: [0, 0, 1] }}>
            <ambientLight intensity={0.4} />
            <directionalLight position={[5, 5, 5]} intensity={0.8} />
            <directionalLight position={[-3, 2, -2]} intensity={0.3} />
            <Environment preset="studio" />
            <Suspense fallback={null}>
              <PartModel url={stlUrl} mode={mode} />
            </Suspense>
            <TrackballControls noZoom={false} noPan={false} noRotate={false} dynamicDampingFactor={0.1} />
          </Canvas>
        </CanvasErrorBoundary>
      </CardContent>
    </Card>
  );
}

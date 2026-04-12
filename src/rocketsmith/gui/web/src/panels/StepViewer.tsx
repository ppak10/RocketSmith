import { Suspense, useRef, useMemo } from "react";
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

interface StepViewerProps {
  /** Relative path to a file in step/. The viewer loads the corresponding STL from stl/. */
  file: string;
}

function StlModel({ url }: { url: string }) {
  const geometry = useLoader(STLLoader, url);
  const ref = useRef<Group>(null);

  // Center and normalize the geometry.
  const centered = useMemo(() => {
    geometry.computeBoundingBox();
    geometry.center();
    const box = geometry.boundingBox!;
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);
    if (maxDim > 0) geometry.scale(3 / maxDim, 3 / maxDim, 3 / maxDim);
    geometry.computeVertexNormals();
    return geometry;
  }, [geometry]);

  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.3;
  });

  return (
    <Center>
      <group ref={ref}>
        <mesh geometry={centered}>
          <meshStandardMaterial
            color="#cccccc"
            metalness={0.1}
            roughness={0.6}
            side={THREE.DoubleSide}
          />
        </mesh>
      </group>
    </Center>
  );
}

export function StepViewer({ file }: StepViewerProps) {
  // Convert step/nose_cone.step → stl/nose_cone.stl
  const stlPath = file
    .replace(/^step\//, "stl/")
    .replace(/\.step$/i, ".stl");
  const stlUrl = `${apiBase()}/api/files/${stlPath}`;
  const filename = file.split("/").pop() ?? file;

  return (
    <Card className="flex flex-col m-4">
      <CardHeader>
        <CardTitle className="text-sm">{filename}</CardTitle>
        <p className="text-xs text-foreground/50">{file}</p>
      </CardHeader>
      <CardContent className="flex-1 min-h-0">
        <div className="h-full w-full rounded-base border-2 border-border bg-secondary-background overflow-hidden">
          <Canvas camera={{ position: [0, 0, 5], fov: 45 }}>
            <ambientLight intensity={0.4} />
            <directionalLight position={[5, 5, 5]} intensity={0.8} />
            <directionalLight position={[-3, 2, -2]} intensity={0.3} />
            <Environment preset="studio" />
            <Suspense fallback={null}>
              <StlModel url={stlUrl} />
            </Suspense>
            <OrbitControls enableDamping dampingFactor={0.1} />
          </Canvas>
        </div>
      </CardContent>
    </Card>
  );
}

import { useMemo } from "react";

// ── Types ──────────────────────────────────────────────────────────────────

type Qty = [number, string];

export interface ComponentNode {
  type: string;
  name: string;
  category: string;
  dimensions: Record<string, unknown>;
  mass: Qty | null;
  override_mass: Qty | null;
  override_mass_enabled: boolean;
  material: string | null;
  human_notes: string | null;
  agent: {
    fate: string;
    fused_into: string | null;
    reason: string | null;
    dfam_shoulder_length_mm?: number | null;
    dfam_shoulder_od_mm?: number | null;
    dfam_hollow?: boolean;
    dfam_wall_mm?: number | null;
  } | null;
  cost: number | null;
  step_path: string | null;
  children: ComponentNode[];
}

export interface Stage {
  name: string;
  components: ComponentNode[];
  cg?: Qty | null;
  cp?: Qty | null;
  stability_cal?: number | null;
  max_diameter?: Qty | null;
}

// ── Shape building ─────────────────────────────────────────────────────────

interface Shape {
  type: string;
  name: string;
  x: number;
  length: number;
  radius: number;
  innerRadius?: number;
  tipRadius?: number;
  aftRadius?: number;
  finSpan?: number;
  finSweep?: number;
  finTipChord?: number;
  finCount?: number;
  noseShape?: string;
  color: string;
}

const SHAPE_COLORS: Record<string, string> = {
  NoseCone: "var(--comp-nose)",
  BodyTube: "var(--comp-body)",
  InnerTube: "var(--comp-inner)",
  TrapezoidFinSet: "var(--comp-fin)",
  EllipticalFinSet: "var(--comp-fin)",
  FreeformFinSet: "var(--comp-fin)",
  TubeCoupler: "var(--comp-coupler)",
  Transition: "var(--comp-transition)",
  Parachute: "var(--comp-recovery)",
  Streamer: "var(--comp-recovery)",
  ShockCord: "var(--comp-recovery)",
  CenteringRing: "var(--comp-ring)",
  BulkHead: "var(--comp-ring)",
  EngineBlock: "var(--comp-ring)",
  MassComponent: "var(--comp-ring)",
  LaunchLug: "var(--comp-lug)",
  RailButton: "var(--comp-lug)",
};

function dimVal(dims: Record<string, unknown>, key: string): number {
  const v = dims[key];
  if (Array.isArray(v)) return v[0] as number;
  if (typeof v === "number") return v;
  return 0;
}

/** Find the sibling InnerTube (motor mount) to derive centering ring positions. */
function findMotorMount(siblings: ComponentNode[]): { x: number; length: number; radius: number } | null {
  for (const s of siblings) {
    if (s.type === "InnerTube") {
      const d = s.dimensions as Record<string, unknown>;
      return { x: 0, length: dimVal(d, "length"), radius: dimVal(d, "od") / 2 };
    }
  }
  return null;
}

function buildShapes(stages: Stage[]): Shape[] {
  const shapes: Shape[] = [];
  let cursor = 0;

  function walkComponents(components: ComponentNode[], parentX: number, parentLength: number, parentRadius: number) {
    // Pre-compute motor mount position for centering ring placement.
    const mount = findMotorMount(components);
    const mountX = mount ? parentX + parentLength - mount.length : null;
    const mountEnd = mount ? parentX + parentLength : null;
    const mountRadius = mount?.radius ?? parentRadius * 0.5;
    // Track centering ring index to distribute forward/aft.
    let ringIndex = 0;

    for (const comp of components) {
      const dims = comp.dimensions as Record<string, unknown>;

      if (comp.type === "NoseCone") {
        const length = dimVal(dims, "length");
        const radius = dimVal(dims, "base_od") / 2;
        const noseShape = typeof dims.shape === "string" ? dims.shape : "ogive";
        shapes.push({ type: "NoseCone", name: comp.name, x: cursor, length, radius, tipRadius: 0, noseShape, color: SHAPE_COLORS.NoseCone });
        cursor += length;
        walkComponents(comp.children, cursor - length, length, radius);
      } else if (comp.type === "BodyTube") {
        const length = dimVal(dims, "length");
        const radius = dimVal(dims, "od") / 2;
        shapes.push({ type: "BodyTube", name: comp.name, x: cursor, length, radius, innerRadius: dimVal(dims, "id") / 2, color: SHAPE_COLORS.BodyTube });
        const tubeX = cursor;
        cursor += length;
        walkComponents(comp.children, tubeX, length, radius);
      } else if (comp.type === "TubeCoupler") {
        const length = dimVal(dims, "length");
        const radius = dimVal(dims, "od") / 2;
        shapes.push({ type: "TubeCoupler", name: comp.name, x: cursor, length, radius, color: SHAPE_COLORS.TubeCoupler });
      } else if (comp.type === "InnerTube") {
        const length = dimVal(dims, "length");
        const radius = dimVal(dims, "od") / 2;
        const x = parentX + parentLength - length;
        shapes.push({ type: "InnerTube", name: comp.name, x, length, radius, innerRadius: dimVal(dims, "id") / 2, color: SHAPE_COLORS.InnerTube });
      } else if (comp.type === "Transition") {
        const length = dimVal(dims, "length");
        const foreRadius = dimVal(dims, "fore_od") / 2;
        const aftRadius = dimVal(dims, "aft_od") / 2;
        shapes.push({ type: "Transition", name: comp.name, x: cursor, length, radius: foreRadius, aftRadius, color: SHAPE_COLORS.Transition });
        cursor += length;
        walkComponents(comp.children, cursor - length, length, aftRadius);
      } else if (comp.type.includes("FinSet")) {
        const rootChord = dimVal(dims, "root_chord");
        const span = dimVal(dims, "span");
        const sweep = dimVal(dims, "sweep");
        const tipChord = dimVal(dims, "tip_chord");
        const count = dimVal(dims, "count") || 3;
        const x = parentX + parentLength - rootChord;
        shapes.push({ type: comp.type, name: comp.name, x, length: rootChord, radius: parentRadius, finSpan: span, finSweep: sweep, finTipChord: tipChord, finCount: count, color: SHAPE_COLORS.TrapezoidFinSet });
      } else if (comp.type === "Parachute") {
        const diameter = dimVal(dims, "diameter");
        const iconLen = Math.min(diameter * 0.1, parentLength * 0.15) || 10;
        const x = parentX + parentLength * 0.3;
        shapes.push({ type: "Parachute", name: comp.name, x, length: iconLen, radius: parentRadius * 0.5, color: SHAPE_COLORS.Parachute });
      } else if (comp.type === "CenteringRing" || (comp.type === "MassComponent" && comp.name.toLowerCase().includes("centering"))) {
        const ringThickness = 3;
        let x: number;
        if (mountX != null && mountEnd != null) {
          // Place first ring at forward end of motor mount, second at aft end.
          x = ringIndex === 0 ? mountX : mountEnd - ringThickness;
        } else {
          // Fallback: spread evenly along the parent.
          x = parentX + parentLength * (ringIndex === 0 ? 0.4 : 0.9);
        }
        ringIndex++;
        shapes.push({ type: "CenteringRing", name: comp.name, x, length: ringThickness, radius: parentRadius, innerRadius: mountRadius, color: SHAPE_COLORS.CenteringRing });
      } else if (comp.type === "LaunchLug" || (comp.type === "MassComponent" && comp.name.toLowerCase().includes("launch lug"))) {
        // Launch lug: small tube on the outside of the body.
        const lugLength = dimVal(dims, "length") || parentLength * 0.08;
        const lugHeight = parentRadius * 0.25;
        const axialOffset = dimVal(dims, "axial_offset");
        const x = axialOffset > 0 ? axialOffset : parentX + (parentLength - lugLength) / 2;
        shapes.push({ type: "LaunchLug", name: comp.name, x, length: lugLength, radius: parentRadius + lugHeight, innerRadius: parentRadius, color: SHAPE_COLORS.LaunchLug });
      } else if (comp.type === "RailButton") {
        // Rail button: small protrusion on the body surface, positioned at its actual axial location.
        const btnHeight = dimVal(dims, "height") || parentRadius * 0.2;
        const btnLength = dimVal(dims, "outer_diameter") || parentRadius * 0.15;
        const axialOffset = dimVal(dims, "axial_offset");
        const x = axialOffset > 0 ? axialOffset : parentX + (parentLength - btnLength) / 2;
        shapes.push({ type: "RailButton", name: comp.name, x, length: btnLength, radius: parentRadius + btnHeight, innerRadius: parentRadius, color: SHAPE_COLORS.RailButton });
      } else if (comp.type === "BulkHead") {
        // Bulkhead: thin solid disc spanning the inner diameter.
        const thickness = 3;
        const x = parentX + parentLength * 0.5;
        shapes.push({ type: "BulkHead", name: comp.name, x, length: thickness, radius: parentRadius, innerRadius: 0, color: SHAPE_COLORS.BulkHead });
      } else if (comp.type === "EngineBlock") {
        // Engine block: thin ring at the aft end of a motor mount.
        const thickness = 3;
        const x = parentX + parentLength - thickness;
        const innerR = mountRadius * 0.7;
        shapes.push({ type: "EngineBlock", name: comp.name, x, length: thickness, radius: parentRadius, innerRadius: innerR, color: SHAPE_COLORS.EngineBlock });
      } else if (comp.type === "Streamer") {
        // Streamer: small dashed rectangle inside the body, like a packed parachute.
        const iconLen = parentLength * 0.12;
        const x = parentX + parentLength * 0.4;
        shapes.push({ type: "Streamer", name: comp.name, x, length: iconLen, radius: parentRadius * 0.4, color: SHAPE_COLORS.Streamer });
      }

      // Recurse into children for any component type not already handled above.
      if (!["NoseCone", "BodyTube", "TubeCoupler", "InnerTube", "Transition"].includes(comp.type) && !comp.type.includes("FinSet")) {
        walkComponents(comp.children, parentX, parentLength, parentRadius);
      }
    }
  }

  for (const stage of stages) {
    walkComponents(stage.components, 0, 0, 0);
  }
  return shapes;
}

// ── Nose cone profile generators ──────────────────────────────────────────
// Each function returns an array of [x, y] points from tip (0,0) to base (1,1)
// where x is fraction of length and y is fraction of radius.

function noseProfile(shape: string, n = 64): [number, number][] {
  const pts: [number, number][] = [];
  for (let i = 0; i <= n; i++) {
    // Cosine spacing: denser near tip (t=0) where curvature is highest.
    const t = 0.5 * (1 - Math.cos((Math.PI * i) / n));
    let y: number;
    switch (shape) {
      case "conical":
        y = t;
        break;
      case "ellipsoid": {
        y = Math.sqrt(1 - (1 - t) * (1 - t));
        break;
      }
      case "power": {
        // Power series with exponent 0.5 (square root — blunted shape)
        y = Math.sqrt(t);
        break;
      }
      case "parabolic": {
        // Parabolic series with k=0.5
        const k = 0.5;
        y = (2 * t - k * t * t) / (2 - k);
        break;
      }
      case "haack": {
        // LD-Haack (Von Kármán) series, C = 0
        const theta = Math.acos(1 - 2 * t);
        y = Math.sqrt((theta - Math.sin(2 * theta) / 2) / Math.PI);
        break;
      }
      default:
        // "ogive" — tangent ogive (default)
        // rho = (R^2 + L^2) / (2*R), using normalized coords (R=1, L=1)
        {
          const rho = (1 + 1) / (2 * 1); // = 1
          y = Math.sqrt(rho * rho - (1 - t) * (1 - t)) - (rho - 1);
        }
        break;
    }
    pts.push([t, Math.max(0, Math.min(1, y))]);
  }
  return pts;
}

// ── Component ──────────────────────────────────────────────────────────────

interface RocketProfileProps {
  stages: Stage[];
  cgMm?: number | null;
  cpMm?: number | null;
  highlightedName?: string | null;
}

export function RocketProfile({ stages, cgMm = null, cpMm = null, highlightedName = null }: RocketProfileProps) {
  const shapes = useMemo(() => buildShapes(stages), [stages]);

  if (shapes.length === 0) return null;

  const totalLength = Math.max(...shapes.map((s) => s.x + s.length));
  const maxRadius = Math.max(...shapes.map((s) => s.radius + (s.finSpan ?? 0)));

  const padding = 10;
  const svgWidth = 800;
  const scale = (svgWidth - padding * 2) / totalLength;
  const svgHeight = maxRadius * 2 * scale + padding * 2 + 50;
  const centerY = padding + maxRadius * scale;

  return (
    <svg
      viewBox={`0 0 ${svgWidth} ${svgHeight}`}
      className="w-full"
      preserveAspectRatio="xMidYMid meet"
    >
      {/* Center line */}
      <line
        x1={padding}
        y1={centerY}
        x2={padding + totalLength * scale}
        y2={centerY}
        stroke="var(--border)"
        strokeWidth={0.5}
        strokeDasharray="4 2"
      />

      {shapes.map((shape, i) => {
        const sx = padding + shape.x * scale;
        const sl = shape.length * scale;
        const sr = shape.radius * scale;
        const isActive = highlightedName != null;
        const isHit = highlightedName === shape.name;
        const dimOpacity = isActive && !isHit ? 0.3 : 1;
        const highlightStroke = isHit ? "var(--foreground)" : "var(--border)";
        const highlightStrokeWidth = isHit ? 2.5 : 1.5;

        if (shape.type === "NoseCone") {
          const pts = noseProfile(shape.noseShape ?? "ogive");
          // Upper outline: tip to base
          const upper = pts.map(([t, r], idx) => {
            const px = sx + t * sl;
            const py = centerY - r * sr;
            return idx === 0 ? `M ${px} ${py}` : `L ${px} ${py}`;
          }).join(" ");
          // Lower outline: base back to tip (reversed)
          const lower = [...pts].reverse().map(([t, r]) => {
            const px = sx + t * sl;
            const py = centerY + r * sr;
            return `L ${px} ${py}`;
          }).join(" ");
          return (
            <g key={i} opacity={dimOpacity} className="transition-opacity">
              <path
                d={`${upper} ${lower} Z`}
                fill={shape.color}
                stroke={highlightStroke}
                strokeWidth={highlightStrokeWidth}
              />
            </g>
          );
        }

        if (shape.type === "BodyTube" || shape.type === "TubeCoupler") {
          return (
            <g key={i} opacity={dimOpacity} className="transition-opacity">
              <rect x={sx} y={centerY - sr} width={sl} height={sr * 2} fill={shape.color} stroke={highlightStroke} strokeWidth={highlightStrokeWidth} />
            </g>
          );
        }

        if (shape.type === "InnerTube") {
          return (
            <g key={i} opacity={dimOpacity} className="transition-opacity">
              <rect x={sx} y={centerY - sr} width={sl} height={sr * 2} fill={shape.color} fillOpacity={0.5} stroke={isHit ? highlightStroke : "var(--border)"} strokeWidth={isHit ? highlightStrokeWidth : 1} strokeDasharray={isHit ? undefined : "3 2"} />
            </g>
          );
        }

        if (shape.type === "Transition") {
          const aftR = (shape.aftRadius ?? sr) * scale;
          return (
            <g key={i} opacity={dimOpacity} className="transition-opacity">
              <path
                d={`M ${sx} ${centerY - sr} L ${sx + sl} ${centerY - aftR} L ${sx + sl} ${centerY + aftR} L ${sx} ${centerY + sr} Z`}
                fill={shape.color}
                stroke={highlightStroke}
                strokeWidth={highlightStrokeWidth}
              />
            </g>
          );
        }

        if (shape.type.includes("FinSet") && shape.finSpan) {
          const finSpanPx = shape.finSpan * scale;
          const sweepPx = (shape.finSweep ?? 0) * scale;
          const tipChordPx = (shape.finTipChord ?? 0) * scale;
          const ux1 = sx;
          const uy1 = centerY - sr;
          const ly1 = centerY + sr;
          return (
            <g key={i} opacity={dimOpacity} className="transition-opacity">
              <path d={`M ${ux1} ${uy1} L ${ux1 + sweepPx} ${uy1 - finSpanPx} L ${ux1 + sweepPx + tipChordPx} ${uy1 - finSpanPx} L ${ux1 + sl} ${uy1} Z`} fill={shape.color} stroke={highlightStroke} strokeWidth={highlightStrokeWidth} />
              <path d={`M ${ux1} ${ly1} L ${ux1 + sweepPx} ${ly1 + finSpanPx} L ${ux1 + sweepPx + tipChordPx} ${ly1 + finSpanPx} L ${ux1 + sl} ${ly1} Z`} fill={shape.color} stroke={highlightStroke} strokeWidth={highlightStrokeWidth} />
            </g>
          );
        }

        if (shape.type === "Parachute") {
          return (
            <g key={i} opacity={dimOpacity} className="transition-opacity">
              <rect
                x={sx}
                y={centerY - sr}
                width={sl}
                height={sr * 2}
                fill={shape.color}
                fillOpacity={isHit ? 0.35 : 0.15}
                stroke={isHit ? highlightStroke : shape.color}
                strokeWidth={highlightStrokeWidth}
                strokeDasharray={isHit ? undefined : "4 3"}
              />
            </g>
          );
        }

        if (shape.type === "CenteringRing") {
          const ir = (shape.innerRadius ?? 0) * scale;
          return (
            <g key={i} opacity={dimOpacity} className="transition-opacity">
              <rect x={sx} y={centerY - sr} width={sl} height={sr - ir} fill={shape.color} fillOpacity={isHit ? 1 : 0.8} stroke={highlightStroke} strokeWidth={isHit ? highlightStrokeWidth : 0.75} />
              <rect x={sx} y={centerY + ir} width={sl} height={sr - ir} fill={shape.color} fillOpacity={isHit ? 1 : 0.8} stroke={highlightStroke} strokeWidth={isHit ? highlightStrokeWidth : 0.75} />
            </g>
          );
        }

        if (shape.type === "LaunchLug") {
          // Small rectangle protruding from the body tube (top side only).
          const ir = (shape.innerRadius ?? 0) * scale;
          const lugH = sr - ir;
          return (
            <g key={i} opacity={dimOpacity} className="transition-opacity">
              <rect
                x={sx}
                y={centerY - sr}
                width={sl}
                height={lugH}
                fill={shape.color}
                stroke={highlightStroke}
                strokeWidth={isHit ? highlightStrokeWidth : 1}
                rx={1}
              />
            </g>
          );
        }

        if (shape.type === "RailButton") {
          // Small circle protruding from the body tube (top side only).
          const ir = (shape.innerRadius ?? 0) * scale;
          const btnH = sr - ir;
          return (
            <g key={i} opacity={dimOpacity} className="transition-opacity">
              <rect
                x={sx}
                y={centerY - sr}
                width={sl}
                height={btnH}
                fill={shape.color}
                stroke={highlightStroke}
                strokeWidth={isHit ? highlightStrokeWidth : 1}
                rx={Math.min(sl, btnH) / 2}
              />
            </g>
          );
        }

        if (shape.type === "BulkHead") {
          // Thin filled disc spanning the tube bore.
          return (
            <g key={i} opacity={dimOpacity} className="transition-opacity">
              <rect
                x={sx}
                y={centerY - sr}
                width={sl}
                height={sr * 2}
                fill={shape.color}
                fillOpacity={isHit ? 1 : 0.85}
                stroke={highlightStroke}
                strokeWidth={isHit ? highlightStrokeWidth : 0.75}
              />
            </g>
          );
        }

        if (shape.type === "EngineBlock") {
          const ir = (shape.innerRadius ?? 0) * scale;
          return (
            <g key={i} opacity={dimOpacity} className="transition-opacity">
              <rect x={sx} y={centerY - sr} width={sl} height={sr - ir} fill={shape.color} fillOpacity={isHit ? 1 : 0.8} stroke={highlightStroke} strokeWidth={isHit ? highlightStrokeWidth : 0.75} />
              <rect x={sx} y={centerY + ir} width={sl} height={sr - ir} fill={shape.color} fillOpacity={isHit ? 1 : 0.8} stroke={highlightStroke} strokeWidth={isHit ? highlightStrokeWidth : 0.75} />
            </g>
          );
        }

        if (shape.type === "Streamer") {
          return (
            <g key={i} opacity={dimOpacity} className="transition-opacity">
              <rect
                x={sx}
                y={centerY - sr}
                width={sl}
                height={sr * 2}
                fill={shape.color}
                fillOpacity={isHit ? 0.3 : 0.1}
                stroke={isHit ? highlightStroke : shape.color}
                strokeWidth={highlightStrokeWidth}
                strokeDasharray={isHit ? undefined : "3 2"}
              />
            </g>
          );
        }

        return null;
      })}

      {/* CG marker */}
      {cgMm != null && (
        <g transform={`translate(${padding + cgMm * scale}, ${centerY})`}>
          <circle r={6} fill="none" stroke="var(--comp-cg)" strokeWidth={1.5} />
          <line x1={-3.5} y1={0} x2={3.5} y2={0} stroke="var(--comp-cg)" strokeWidth={1.5} />
          <line x1={0} y1={-3.5} x2={0} y2={3.5} stroke="var(--comp-cg)" strokeWidth={1.5} />
        </g>
      )}

      {/* CP marker */}
      {cpMm != null && (
        <g transform={`translate(${padding + cpMm * scale}, ${centerY})`}>
          <circle r={6} fill="none" stroke="var(--comp-cp)" strokeWidth={1.5} />
          <circle r={2} fill="var(--comp-cp)" />
        </g>
      )}

      {/* Dimension line */}
      <g>
        <line
          x1={padding} y1={svgHeight - 8}
          x2={padding + totalLength * scale} y2={svgHeight - 8}
          stroke="var(--foreground)" strokeWidth={0.75}
          markerStart="url(#arrowL)" markerEnd="url(#arrowR)"
        />
        <text x={padding + (totalLength * scale) / 2} y={svgHeight - 12} textAnchor="middle" fontSize={9} fill="var(--foreground)" opacity={0.5}>
          {totalLength.toFixed(0)} mm
        </text>
      </g>

      <defs>
        <marker id="arrowL" markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto">
          <path d="M 6 0 L 0 3 L 6 6" fill="none" stroke="var(--foreground)" strokeWidth="0.75" />
        </marker>
        <marker id="arrowR" markerWidth="6" markerHeight="6" refX="0" refY="3" orient="auto">
          <path d="M 0 0 L 6 3 L 0 6" fill="none" stroke="var(--foreground)" strokeWidth="0.75" />
        </marker>
      </defs>
    </svg>
  );
}

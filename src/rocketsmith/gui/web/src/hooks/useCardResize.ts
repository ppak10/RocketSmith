import { useCallback, useRef, useState } from "react";
import { GRID_COL_MIN, GRID_ROW_H, GRID_GAP } from "@/layout/cardRegistry";

interface UseCardResizeOptions {
  colSpan: number;
  rowSpan: number;
  minColSpan: number;
  maxColSpan: number;
  minRowSpan: number;
  maxRowSpan: number;
  /** Current number of grid columns — used to cap maxColSpan. */
  gridCols: number;
  onResizeEnd: (colSpan: number, rowSpan: number) => void;
}

export function useCardResize({
  colSpan,
  rowSpan,
  minColSpan,
  maxColSpan,
  minRowSpan,
  maxRowSpan,
  gridCols,
  onResizeEnd,
}: UseCardResizeOptions) {
  const [isResizing, setIsResizing] = useState(false);
  const [previewColSpan, setPreviewColSpan] = useState(colSpan);
  const [previewRowSpan, setPreviewRowSpan] = useState(rowSpan);
  const startRef = useRef({ x: 0, y: 0, colSpan: 0, rowSpan: 0 });

  const cellW = GRID_COL_MIN + GRID_GAP;
  const cellH = GRID_ROW_H + GRID_GAP;

  const clamp = useCallback(
    (cs: number, rs: number) => {
      const effectiveMaxCol = Math.min(maxColSpan, gridCols);
      return {
        cs: Math.max(minColSpan, Math.min(effectiveMaxCol, cs)),
        rs: Math.max(minRowSpan, Math.min(maxRowSpan, rs)),
      };
    },
    [minColSpan, maxColSpan, minRowSpan, maxRowSpan, gridCols],
  );

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.stopPropagation();
      e.preventDefault();
      const target = e.currentTarget as HTMLElement;
      target.setPointerCapture(e.pointerId);

      startRef.current = { x: e.clientX, y: e.clientY, colSpan, rowSpan };
      setPreviewColSpan(colSpan);
      setPreviewRowSpan(rowSpan);
      setIsResizing(true);

      const onMove = (ev: PointerEvent) => {
        const dx = ev.clientX - startRef.current.x;
        const dy = ev.clientY - startRef.current.y;
        const dCols = Math.round(dx / cellW);
        const dRows = Math.round(dy / cellH);
        const { cs, rs } = clamp(
          startRef.current.colSpan + dCols,
          startRef.current.rowSpan + dRows,
        );
        setPreviewColSpan(cs);
        setPreviewRowSpan(rs);
      };

      const onUp = () => {
        target.removeEventListener("pointermove", onMove);
        target.removeEventListener("pointerup", onUp);
        setIsResizing(false);
        // Read latest preview values via the refs' closure.
        const dx2 = 0; // final values already in state
        // Use a microtask to read the final state.
        requestAnimationFrame(() => {
          setPreviewColSpan((cs) => {
            setPreviewRowSpan((rs) => {
              onResizeEnd(cs, rs);
              return rs;
            });
            return cs;
          });
        });
      };

      target.addEventListener("pointermove", onMove);
      target.addEventListener("pointerup", onUp);
    },
    [colSpan, rowSpan, cellW, cellH, clamp, onResizeEnd],
  );

  return {
    isResizing,
    previewColSpan: isResizing ? previewColSpan : colSpan,
    previewRowSpan: isResizing ? previewRowSpan : rowSpan,
    resizeHandleProps: { onPointerDown },
  };
}

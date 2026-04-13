import type { ReactNode } from "react";
import { useDraggable } from "@dnd-kit/core";
import { useCardResize } from "@/hooks/useCardResize";

interface DraggableCardProps {
  id: string;
  children: ReactNode;
  colSpan?: number;
  rowSpan?: number;
  /** 1-based grid column start. Omit for auto-placement. */
  col?: number;
  /** 1-based grid row start. Omit for auto-placement. */
  row?: number;
  /** Current grid column count — for resize max clamping. */
  gridCols?: number;
  /** Min/max constraints. */
  minColSpan?: number;
  maxColSpan?: number;
  minRowSpan?: number;
  maxRowSpan?: number;
  /** Called when resize completes. */
  onResizeEnd?: (colSpan: number, rowSpan: number) => void;
  /** Whether this card is the most recently updated. */
  active?: boolean;
}

export function DraggableCard({
  id,
  children,
  colSpan = 1,
  rowSpan = 1,
  col,
  row,
  gridCols = 3,
  minColSpan = 1,
  maxColSpan = 2,
  minRowSpan = 1,
  maxRowSpan = 3,
  onResizeEnd,
  active = false,
}: DraggableCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    isDragging,
  } = useDraggable({ id });

  const {
    isResizing,
    previewColSpan,
    previewRowSpan,
    resizeHandleProps,
  } = useCardResize({
    colSpan,
    rowSpan,
    minColSpan,
    maxColSpan,
    minRowSpan,
    maxRowSpan,
    gridCols,
    onResizeEnd: onResizeEnd ?? (() => {}),
  });

  const activeColSpan = isResizing ? previewColSpan : colSpan;
  const activeRowSpan = isResizing ? previewRowSpan : rowSpan;

  const style: React.CSSProperties = {
    ...(col
      ? { gridColumn: `${col} / span ${activeColSpan}` }
      : { gridColumn: `span ${activeColSpan}` }),
    ...(row
      ? { gridRow: `${row} / span ${activeRowSpan}` }
      : { gridRow: `span ${activeRowSpan}` }),
  };

  return (
    <div
      ref={setNodeRef}
      data-card-id={id}
      style={style}
      className={`relative cursor-grab rounded-base active:cursor-grabbing ${active ? "[&>*[data-slot=card]]:border-orange-500" : ""} ${isDragging ? "z-50 opacity-60 ring-2 ring-main" : ""} ${isResizing ? "z-40" : ""}`}
      {...attributes}
      {...listeners}
    >
      {/* Resize handle — right edge (horizontal) */}
      <div
        className="absolute top-0 right-0 z-10 h-full w-2 cursor-ew-resize opacity-0 transition-opacity [div:hover>&]:opacity-30 hover:opacity-60"
        {...resizeHandleProps}
      >
        <div className="absolute right-0 top-1/2 h-8 w-1 -translate-y-1/2 rounded-full bg-foreground/40" />
      </div>

      {/* Resize handle — bottom edge (vertical) */}
      <div
        className="absolute bottom-0 left-0 z-10 h-2 w-full cursor-ns-resize opacity-0 transition-opacity [div:hover>&]:opacity-30 hover:opacity-60"
        {...resizeHandleProps}
      >
        <div className="absolute bottom-0 left-1/2 h-1 w-8 -translate-x-1/2 rounded-full bg-foreground/40" />
      </div>

      {children}
    </div>
  );
}

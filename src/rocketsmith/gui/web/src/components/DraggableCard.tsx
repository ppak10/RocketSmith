import type { ReactNode } from "react";
import { useDraggable } from "@dnd-kit/core";
import { GripVertical } from "lucide-react";
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
    ...(transform && !isResizing
      ? { transform: `translate(${transform.x}px, ${transform.y}px)` }
      : {}),
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
      style={style}
      className={`relative rounded-base ${active ? "ring-2 ring-orange-500" : ""} ${isDragging ? "z-50 opacity-50" : ""} ${isResizing ? "z-40" : ""}`}
    >
      {/* Drag handle — top right */}
      <button
        type="button"
        className="absolute right-2 top-2 z-10 cursor-grab rounded-base border-2 border-border bg-main p-1 text-main-foreground opacity-0 transition-opacity hover:opacity-100 focus-visible:opacity-100 active:cursor-grabbing [div:hover>&]:opacity-70"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="size-4" />
      </button>

      {/* Resize handle — bottom right */}
      <div
        className="absolute bottom-1 right-1 z-10 cursor-nwse-resize opacity-0 transition-opacity [div:hover>&]:opacity-70 hover:opacity-100"
        {...resizeHandleProps}
      >
        <svg width="12" height="12" viewBox="0 0 12 12" className="text-foreground/40">
          <path d="M11 1L1 11M11 5L5 11M11 9L9 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>

      {children}
    </div>
  );
}

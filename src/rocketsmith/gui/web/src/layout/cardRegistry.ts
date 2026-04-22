// Grid constants — shared by ActiveView, DraggableCard, and useCardResize.
export const GRID_COL_MIN = 280;
export const GRID_ROW_H = 180;
export const GRID_GAP = 16;

export interface CardDefinition {
  id: string;
  label: string;
  defaultOrder: number;
  /** Default column span. */
  colSpan?: number;
  /** Default row span. */
  rowSpan?: number;
  minColSpan?: number;
  maxColSpan?: number;
  minRowSpan?: number;
  maxRowSpan?: number;
}

/** Defaults for dynamically created part cards (part-{stem}). */
const PART_CARD_DEFAULTS: Omit<CardDefinition, "id" | "label" | "defaultOrder"> = {
  colSpan: 3,
  rowSpan: 4,
  minColSpan: 2,
  maxColSpan: 4,
  minRowSpan: 3,
  maxRowSpan: 5,
};

export const CARD_REGISTRY: CardDefinition[] = [
  { id: "assembly", label: "Assembly", defaultOrder: 1, colSpan: 3, rowSpan: 3, minColSpan: 2, maxColSpan: 4, minRowSpan: 2, maxRowSpan: 4 },
  { id: "flight", label: "Flight", defaultOrder: 2, colSpan: 3, rowSpan: 3, minColSpan: 2, maxColSpan: 4, minRowSpan: 2, maxRowSpan: 5 },
  {
    id: "session-log",
    label: "Session Log",
    defaultOrder: 3,
    colSpan: 2,
    rowSpan: 4,
    minColSpan: 2,
    maxColSpan: 2,
    minRowSpan: 1,
    maxRowSpan: 8
  },
];

export const DEFAULT_ORDER = CARD_REGISTRY.map((c) => c.id);

/** Lookup card definition by ID. Dynamic part-{stem} cards get shared defaults. */
export function getCardDef(id: string): CardDefinition {
  const found = CARD_REGISTRY.find((c) => c.id === id);
  if (found) return found;

  // Dynamic part cards.
  if (id.startsWith("part-")) {
    return {
      id,
      label: id.replace("part-", "").replace(/_/g, " "),
      defaultOrder: 0,
      ...PART_CARD_DEFAULTS,
    };
  }

  // Fallback.
  return { id, label: id, defaultOrder: 99, colSpan: 1, rowSpan: 1, minColSpan: 1, maxColSpan: 2, minRowSpan: 1, maxRowSpan: 3 };
}

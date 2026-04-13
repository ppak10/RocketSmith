import { useState, useCallback } from "react";

const STORAGE_KEY = "rocketsmith:preferences";

/** Stored grid layout for a card — position and size. */
export interface CardLayout {
  col: number;
  row: number;
  colSpan: number;
  rowSpan: number;
}

interface Preferences {
  /** Map of card ID → grid layout. Empty = auto-place with default spans. */
  agentFeedLayout: Record<string, CardLayout>;
}

const DEFAULTS: Preferences = {
  agentFeedLayout: {},
};

function readPreferences(): Preferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw);
    return { ...DEFAULTS, ...parsed };
  } catch {
    return DEFAULTS;
  }
}

function writePreferences(prefs: Preferences): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // localStorage full or unavailable — silently ignore.
  }
}

export function usePreferences() {
  const [prefs, setPrefs] = useState<Preferences>(readPreferences);

  const setAgentFeedLayout = useCallback(
    (layout: Record<string, CardLayout>) => {
      setPrefs((prev) => {
        const next = { ...prev, agentFeedLayout: layout };
        writePreferences(next);
        return next;
      });
    },
    [],
  );

  return {
    agentFeedLayout: prefs.agentFeedLayout,
    setAgentFeedLayout,
  };
}

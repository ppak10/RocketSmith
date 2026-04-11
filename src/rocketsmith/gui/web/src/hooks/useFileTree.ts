import { useEffect, useState, useCallback } from "react";
import { apiBase } from "@/lib/server";
import type { WatchEvent } from "./useWatchSocket";

export interface FileNode {
  name: string;
  type: "file" | "directory";
  path: string;
  children?: FileNode[];
}

/**
 * Fetches the project file tree from the server.
 * Re-fetches when file events arrive (debounced).
 */
export function useFileTree(events: WatchEvent[]): FileNode[] {
  const [tree, setTree] = useState<FileNode[]>([]);

  const fetchTree = useCallback(() => {
    fetch(`${apiBase()}/api/files-tree`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setTree)
      .catch(() => {});
  }, []);

  // Fetch on mount.
  useEffect(() => {
    fetchTree();
  }, [fetchTree]);

  // Re-fetch when events arrive (debounced to avoid spamming).
  useEffect(() => {
    if (events.length === 0) return;
    const timer = setTimeout(fetchTree, 1000);
    return () => clearTimeout(timer);
  }, [events.length, fetchTree]);

  return tree;
}

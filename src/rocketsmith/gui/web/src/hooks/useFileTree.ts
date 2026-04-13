import { useEffect, useState } from "react";
import { getOfflineFilesTree } from "@/lib/server";

export interface FileNode {
  name: string;
  type: "file" | "directory";
  path: string;
  children?: FileNode[];
}

function readTree(): FileNode[] {
  return (getOfflineFilesTree() as FileNode[]) ?? [];
}

/**
 * Returns the project file tree from the offline data bundle.
 * Re-reads when `treeVersion` bumps (server pushed a tree update over WS).
 */
export function useFileTree(treeVersion: number): FileNode[] {
  const [tree, setTree] = useState<FileNode[]>(readTree);

  useEffect(() => {
    setTree(readTree());
  }, [treeVersion]);

  return tree;
}

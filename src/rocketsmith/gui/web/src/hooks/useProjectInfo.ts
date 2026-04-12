import { getOfflineProjectInfo } from "@/lib/server";

interface ProjectInfo {
  /** Just the directory name, e.g. "v12" */
  name: string;
  /** Full absolute path */
  path: string;
}

function readProjectInfo(): ProjectInfo {
  const offline = getOfflineProjectInfo();
  if (offline) return offline;
  const segments = window.location.pathname.split("/").filter(Boolean);
  const dirName =
    segments.length >= 2 ? segments[segments.length - 2] : "Project";
  return { name: dirName, path: window.location.pathname };
}

/**
 * Returns the project info from the offline data bundle.
 */
export function useProjectInfo(): ProjectInfo {
  return readProjectInfo();
}

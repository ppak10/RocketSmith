import { useState, useEffect } from "react";
import { getOfflineProjectInfo } from "@/lib/server";

interface ProjectInfo {
  /** Just the directory name, e.g. "v12" */
  name: string;
  /** Full absolute path */
  path: string;
}

/**
 * Returns the project info from the offline data bundle.
 */
export function useProjectInfo(): ProjectInfo | null {
  const [info, setInfo] = useState<ProjectInfo | null>(null);

  useEffect(() => {
    const offline = getOfflineProjectInfo();
    if (offline) {
      setInfo(offline);
    } else {
      // Fallback: infer from URL path.
      const segments = window.location.pathname.split("/").filter(Boolean);
      const dirName =
        segments.length >= 2 ? segments[segments.length - 2] : "Project";
      setInfo({ name: dirName, path: window.location.pathname });
    }
  }, []);

  return info;
}

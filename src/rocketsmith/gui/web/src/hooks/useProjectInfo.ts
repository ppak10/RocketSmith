import { useEffect, useState } from "react";
import { apiBase } from "@/lib/server";

interface ProjectInfo {
  /** Just the directory name, e.g. "v12" */
  name: string;
  /** Full absolute path */
  path: string;
}

/**
 * Fetches the project directory from the server.
 * Returns null in offline mode or if the fetch fails.
 */
export function useProjectInfo(): ProjectInfo | null {
  const [info, setInfo] = useState<ProjectInfo | null>(null);

  useEffect(() => {
    fetch(`${apiBase()}/api/project-info`)
      .then((r) => r.json())
      .then((data: { project_dir: string }) => {
        const parts = data.project_dir.split("/");
        const name = parts[parts.length - 1] || data.project_dir;
        setInfo({ name, path: data.project_dir });
      })
      .catch(() => {});
  }, []);

  return info;
}

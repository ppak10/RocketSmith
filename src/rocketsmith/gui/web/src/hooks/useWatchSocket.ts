import { useEffect, useRef, useState, useCallback } from "react";
import {
  wsUrl,
  updateOfflineFile,
  updateOfflineFilesTree,
  updateOfflineProjectInfo,
} from "@/lib/server";

/** Event pushed by the Python watcher over WebSocket. */
export interface WatchEvent {
  /** Category of the changed file. */
  type:
    | "cadsmith"
    | "step"
    | "stl"
    | "parts"
    | "openrocket"
    | "flight"
    | "assembly"
    | "report"
    | "manifest"
    | "image"
    | "preview"
    | "log"
    | "gcode"
    | "prusaslicer"
    | "script"
    | "unknown";
  /** Absolute path to the changed file. */
  path: string;
  /** Path relative to the project root (used for API file fetching). */
  relative_path: string;
  /** Timestamp of the event (ISO 8601). */
  timestamp: string;
  /** Current file content (text files under 100KB only, else null). */
  content: string | null;
  /** Previous file content before this change (null on first change). */
  previous_content: string | null;
}

/** Navigation command sent by the gui_navigate MCP tool. */
export interface NavigateCommand {
  command: "navigate";
  path: string;
}

/** File tree update pushed by the server after snapshot refresh. */
interface FilesTreeUpdate {
  type: "files-tree";
  tree: unknown[];
}

/** Project info pushed by the server on connect (needed in dev/live mode). */
interface ProjectInfoEvent {
  type: "project-info";
  name: string;
  path: string;
}

const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_ATTEMPTS = 5;

/**
 * Reconnecting WebSocket hook that receives file-change events and
 * navigation commands from the Python GUI server.
 *
 * File-change events update the in-memory offline data bundle so that
 * fetchJson/fetchText always return the latest content. Tree updates
 * from the server keep the sidebar file tree current.
 */
export function useWatchSocket() {
  const [events, setEvents] = useState<WatchEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [offline, setOffline] = useState(false);
  const [navigation, setNavigation] = useState<NavigateCommand | null>(null);
  /** Incremented whenever the server pushes a file tree update. */
  const [treeVersion, setTreeVersion] = useState(0);
  const [projectInfo, setProjectInfo] = useState<{ name: string; path: string } | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const attemptsRef = useRef<number>(0);

  const connect = useCallback(() => {
    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setOffline(false);
      attemptsRef.current = 0;
    };

    ws.onclose = () => {
      setConnected(false);
      attemptsRef.current += 1;
      if (attemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
      } else {
        setOffline(true);
      }
    };

    ws.onerror = () => ws.close();

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data);

        if (data.command === "navigate") {
          setNavigation(data as NavigateCommand);
        } else if (data.type === "files-tree") {
          // Server pushed an updated file tree — refresh in-memory bundle.
          const update = data as FilesTreeUpdate;
          updateOfflineFilesTree(update.tree);
          setTreeVersion((v) => v + 1);
        } else if (data.type === "project-info") {
          const info = data as ProjectInfoEvent;
          updateOfflineProjectInfo(info.name, info.path);
          setProjectInfo({ name: info.name, path: info.path });
        } else {
          const event = data as WatchEvent;
          setEvents((prev) => [...prev, event]);
          // Keep the in-memory bundle current.
          if (event.relative_path && event.content !== null) {
            updateOfflineFile(event.relative_path, event.content);
          }
        }
      } catch {
        // Ignore malformed messages.
      }
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const clearNavigation = useCallback(() => setNavigation(null), []);

  return { events, connected, offline, navigation, clearNavigation, treeVersion, projectInfo };
}

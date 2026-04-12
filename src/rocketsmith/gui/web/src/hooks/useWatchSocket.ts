import { useEffect, useRef, useState, useCallback } from "react";
import { wsUrl } from "@/lib/server";

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
    | "gcode"
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


const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_ATTEMPTS = 5;

/**
 * Reconnecting WebSocket hook that receives file-change events and
 * navigation commands from the Python GUI server. When opened via
 * file://, connects to the default backend server.
 */
export function useWatchSocket() {
  const [events, setEvents] = useState<WatchEvent[]>([] as WatchEvent[]);
  const [connected, setConnected] = useState<boolean>(false);
  const [offline, setOffline] = useState<boolean>(false);
  const [navigation, setNavigation] = useState<NavigateCommand | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const attemptsRef = useRef<number>(0);

  const connect = useCallback(() => {
    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
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
        } else {
          setEvents((prev) => [...prev, data as WatchEvent]);
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

  return { events, connected, offline, navigation, clearNavigation };
}

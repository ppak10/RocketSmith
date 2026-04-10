import { useEffect, useRef, useState, useCallback } from "react";

/** Event pushed by the Python watcher over WebSocket. */
export interface WatchEvent {
  /** Category of the changed file. */
  type: "step" | "simulation" | "manifest" | "image" | "unknown";
  /** Absolute path to the changed file. */
  path: string;
  /** Timestamp of the event (ISO 8601). */
  timestamp: string;
}

const WS_URL = `ws://${window.location.host}/ws`;
const RECONNECT_DELAY_MS = 2000;

/**
 * Reconnecting WebSocket hook that receives file-change events from the
 * Python dashboard server.
 */
export function useWatchSocket() {
  const [events, setEvents] = useState<WatchEvent[]>([] as WatchEvent[]);
  const [connected, setConnected] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };

    ws.onerror = () => ws.close();

    ws.onmessage = (msg) => {
      try {
        const event: WatchEvent = JSON.parse(msg.data);
        setEvents((prev) => [...prev, event]);
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

  return { events, connected };
}

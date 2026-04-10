import type { WatchEvent } from "../hooks/useWatchSocket";

interface DashboardProps {
  events: WatchEvent[];
  connected: boolean;
}

export function Dashboard({ events, connected }: DashboardProps) {
  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "1rem" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "1rem",
        }}
      >
        <h1 style={{ margin: 0, fontSize: "1.25rem" }}>RocketSmith</h1>
        <span
          style={{
            fontSize: "0.75rem",
            color: connected ? "#22c55e" : "#ef4444",
          }}
        >
          {connected ? "connected" : "disconnected"}
        </span>
      </header>

      <main>
        {events.length === 0 ? (
          <p style={{ color: "#888" }}>Waiting for file changes...</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {events.map((e, i) => (
              <li
                key={i}
                style={{
                  padding: "0.5rem 0",
                  borderBottom: "1px solid #eee",
                  fontSize: "0.875rem",
                }}
              >
                <strong>{e.type}</strong> {e.path}
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}

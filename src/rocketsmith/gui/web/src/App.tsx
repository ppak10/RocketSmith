import { useWatchSocket } from "./hooks/useWatchSocket";
import { Dashboard } from "./layout/Dashboard";

export function App() {
  const { events, connected } = useWatchSocket();

  return <Dashboard events={events} connected={connected} />;
}

import { useEffect, useState } from "react";
import { useWatchSocket } from "./hooks/useWatchSocket";
import { Dashboard } from "./layout/Dashboard";
import { SidebarProvider } from "@/components/ui/sidebar";

export function App() {
  const { events, connected, offline, navigation } = useWatchSocket();
  const [dark, setDark] = useState(false);
  const [activePanel, setActivePanel] = useState("live");
  const [activeFile, setActiveFile] = useState<string | null>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      setDark(true);
    }
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  // Handle navigation commands from the server.
  useEffect(() => {
    if (navigation) {
      setActivePanel(navigation.panel);
      setActiveFile(navigation.file);
    }
  }, [navigation]);

  return (
    <SidebarProvider>
      <Dashboard
        events={events}
        connected={connected}
        offline={offline}
        dark={dark}
        onToggleTheme={() => setDark((d) => !d)}
        activePanel={activePanel}
        activeFile={activeFile}
        onNavigate={(panel, file) => {
          setActivePanel(panel);
          setActiveFile(file ?? null);
        }}
      />
    </SidebarProvider>
  );
}

import { useEffect, useState } from "react";
import { HashRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useWatchSocket } from "./hooks/useWatchSocket";
import { Dashboard } from "./layout/Dashboard";
import { SidebarProvider } from "@/components/ui/sidebar";
import { ActiveView } from "./layout/ActiveView";
import { FlightViewer } from "@/panels/FlightViewer";
import { AssemblyViewer } from "@/panels/AssemblyViewer";
import { ComponentTreeViewer } from "@/panels/ComponentTreeViewer";
import { PartViewer } from "@/panels/PartViewer";

export function App() {
  const { events, connected, offline, navigation, clearNavigation, treeVersion } = useWatchSocket();
  const [dark, setDark] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      setDark(true);
    }
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  return (
    <HashRouter>
      <SidebarProvider>
        <Routes>
          <Route
            element={
              <Dashboard
                events={events}
                connected={connected}
                offline={offline}
                dark={dark}
                onToggleTheme={() => setDark((d) => !d)}
                navigation={navigation}
                clearNavigation={clearNavigation}
                treeVersion={treeVersion}
              />
            }
          >
            <Route index element={<ActiveView events={events} offline={offline} treeVersion={treeVersion} />} />
            <Route path="flights" element={<FlightViewer treeVersion={treeVersion} />} />
            <Route path="component-tree" element={<ComponentTreeViewer />} />
            <Route path="assembly" element={<AssemblyViewer />} />
            <Route path="parts/*" element={<PartViewerRoute />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </SidebarProvider>
    </HashRouter>
  );
}

function PartViewerRoute() {
  const location = useLocation();
  const path = location.pathname.replace(/^\/parts\//, "parts/");
  return <PartViewer file={decodeURIComponent(path)} />;
}

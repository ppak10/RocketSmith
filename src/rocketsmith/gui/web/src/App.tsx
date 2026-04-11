import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useWatchSocket } from "./hooks/useWatchSocket";
import { Dashboard } from "./layout/Dashboard";
import { SidebarProvider } from "@/components/ui/sidebar";
import { ActiveView } from "./layout/ActiveView";
import { FlightViewer } from "@/panels/FlightViewer";
import { AssemblyViewer } from "@/panels/AssemblyViewer";
import { StepViewer } from "@/panels/StepViewer";
import { FileViewer } from "@/panels/FileViewer";

export function App() {
  const { events, connected, offline, navigation } = useWatchSocket();
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
    <BrowserRouter>
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
              />
            }
          >
            <Route index element={<ActiveView events={events} offline={offline} />} />
            <Route path="flights" element={<FlightViewer events={events} />} />
            <Route path="assembly" element={<AssemblyViewer />} />
            <Route path="file/step/*" element={<StepViewerRoute />} />
            <Route path="file/*" element={<FileViewerRoute />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </SidebarProvider>
    </BrowserRouter>
  );
}

function StepViewerRoute() {
  const path = window.location.pathname.replace("/file/step/", "");
  return <StepViewer file={decodeURIComponent(path)} />;
}

function FileViewerRoute() {
  const path = window.location.pathname.replace("/file/", "");
  return <FileViewer file={decodeURIComponent(path)} />;
}

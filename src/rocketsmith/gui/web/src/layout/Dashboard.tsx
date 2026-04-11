import {
  Moon,
  Sun,
  Rocket,
  Wifi,
  WifiOff,
  Box,
  LineChart,
  Activity,
  MonitorOff,
} from "lucide-react";
import type { WatchEvent } from "../hooks/useWatchSocket";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
  SidebarFooter,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useProjectInfo } from "@/hooks/useProjectInfo";
import { useFileTree } from "@/hooks/useFileTree";
import { ActiveView } from "./ActiveView";
import { FileTree } from "./FileTree";
import { StepViewer } from "@/panels/StepViewer";
import { FileViewer } from "@/panels/FileViewer";
import { SimulationViewer } from "@/panels/SimulationViewer";

interface DashboardProps {
  events: WatchEvent[];
  connected: boolean;
  offline: boolean;
  dark: boolean;
  onToggleTheme: () => void;
  activePanel: string;
  activeFile: string | null;
  onNavigate: (panel: string, file?: string) => void;
}

const NAV_ITEMS = [
  { id: "live", title: "Live", icon: Activity, requiresServer: true },
  {
    id: "simulation",
    title: "Simulation",
    icon: LineChart,
    requiresServer: false,
  },
];

const PANEL_TITLES: Record<string, string> = {
  live: "Live",
  "3d-viewer": "3D Viewer",
  "flight-profile": "Flight Profile",
  simulation: "Simulation",
};

function PanelPlaceholder({
  title,
  file,
}: {
  title: string;
  file: string | null;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex h-48 items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-foreground/40">Coming soon</p>
          {file && (
            <p className="mt-1 text-xs text-foreground/30">{file}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Strip any absolute project-dir prefix from a file path,
 * returning a relative path suitable for API calls.
 */
function toRelative(filePath: string, projectPath: string | null): string {
  if (projectPath && filePath.startsWith(projectPath)) {
    let rel = filePath.slice(projectPath.length);
    if (rel.startsWith("/")) rel = rel.slice(1);
    return rel;
  }
  // Already relative or no project info.
  if (filePath.startsWith("/")) {
    // Best-effort: take everything after the last known layout dir.
    for (const dir of ["parts/", "cadsmith/", "openrocket/", "reports/", "gcode/"]) {
      const idx = filePath.indexOf(dir);
      if (idx >= 0) return filePath.slice(idx);
    }
  }
  return filePath;
}

/** Text-viewable file extensions. */
const TEXT_EXTS = new Set([
  ".py", ".json", ".md", ".csv", ".txt", ".ini",
  ".cfg", ".toml", ".yaml", ".yml", ".gcode",
]);

function getExt(path: string): string {
  const dot = path.lastIndexOf(".");
  return dot >= 0 ? path.slice(dot).toLowerCase() : "";
}

function PanelContent({
  panel,
  file,
  events,
  offline,
  projectPath,
  fileTree,
}: {
  panel: string;
  file: string | null;
  events: WatchEvent[];
  offline: boolean;
  projectPath: string | null;
  fileTree: import("@/hooks/useFileTree").FileNode[];
}) {
  // If a file is selected, route to the appropriate viewer.
  if (file) {
    const ext = getExt(file);
    const relFile = toRelative(file, projectPath);
    if ([".step", ".stp"].includes(ext)) {
      return <StepViewer file={relFile} />;
    }
    if (ext === ".ork") {
      return <SimulationViewer file={relFile} fileTree={fileTree} />;
    }
    if (TEXT_EXTS.has(ext)) {
      return <FileViewer file={relFile} />;
    }
  }

  switch (panel) {
    case "live":
      return <ActiveView events={events} offline={offline} />;
    case "3d-viewer":
      return (
        <PanelPlaceholder
          title="3D Viewer"
          file={null}
        />
      );
    default:
      return (
        <PanelPlaceholder
          title={PANEL_TITLES[panel] ?? panel}
          file={file}
        />
      );
  }
}

export function Dashboard({
  events,
  connected,
  offline,
  dark,
  onToggleTheme,
  activePanel,
  activeFile,
  onNavigate,
}: DashboardProps) {
  const project = useProjectInfo();
  const fileTree = useFileTree(events);

  return (
    <TooltipProvider>
      <Sidebar>
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg">
                <div className="flex aspect-square size-8 items-center justify-center rounded-base border-2 border-border bg-main text-main-foreground">
                  <Rocket className="size-4" />
                </div>
                <div className="flex flex-col gap-0.5 leading-none">
                  <span className="font-heading">RocketSmith</span>
                  <span className="text-xs">Dashboard</span>
                </div>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>
              {project ? project.name : "Panels"}
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {NAV_ITEMS.map((item) => {
                  const disabled = offline && item.requiresServer;
                  return (
                    <SidebarMenuItem key={item.id}>
                      <SidebarMenuButton
                        isActive={activePanel === item.id}
                        className={
                          disabled ? "opacity-40 pointer-events-none" : ""
                        }
                        onClick={() => !disabled && onNavigate(item.id)}
                      >
                        <item.icon className="size-4" />
                        <span>{item.title}</span>
                        {disabled && (
                          <MonitorOff className="ml-auto size-3 text-foreground/30" />
                        )}
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>

          {!offline && fileTree.length > 0 && (
            <SidebarGroup>
              <SidebarGroupLabel>Files</SidebarGroupLabel>
              <SidebarGroupContent>
                <FileTree
                  tree={fileTree}
                  onSelect={(path) => {
                    const ext = path.slice(path.lastIndexOf(".")).toLowerCase();
                    if (ext === ".ork") {
                      onNavigate("simulation", path);
                    } else if ([".step", ".stp"].includes(ext)) {
                      onNavigate("live", path);
                    } else {
                      onNavigate("live", path);
                    }
                  }}
                />
              </SidebarGroupContent>
            </SidebarGroup>
          )}
        </SidebarContent>

        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <div className="flex items-center justify-start px-2 py-1">
                <Button variant="neutral" size="icon" onClick={onToggleTheme}>
                  {dark ? (
                    <Sun className="h-4 w-4" />
                  ) : (
                    <Moon className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>

      <SidebarInset>
        <header className="flex items-center gap-2 border-b-2 border-border bg-background px-4 py-2">
          <SidebarTrigger />
          <h2 className="text-sm font-heading text-foreground">
            {PANEL_TITLES[activePanel] ?? activePanel}
          </h2>
          {activeFile && (
            <span className="text-xs text-foreground/50">{activeFile}</span>
          )}
          <div className="ml-auto">
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant={connected ? "neutral" : "default"}>
                  {offline ? (
                    <>
                      <MonitorOff className="h-3 w-3" />
                      offline
                    </>
                  ) : connected ? (
                    <>
                      <Wifi className="h-3 w-3" />
                      connected
                    </>
                  ) : (
                    <>
                      <WifiOff className="h-3 w-3" />
                      disconnected
                    </>
                  )}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                {offline
                  ? "Running in offline mode — no server connection"
                  : connected
                    ? "Receiving file-change events"
                    : "Attempting to reconnect..."}
              </TooltipContent>
            </Tooltip>
          </div>
        </header>

        <main className="flex-1 overflow-hidden p-4">
          <PanelContent
            panel={activePanel}
            file={activeFile}
            events={events}
            offline={offline}
            projectPath={project?.path ?? null}
            fileTree={fileTree}
          />
        </main>
      </SidebarInset>
    </TooltipProvider>
  );
}

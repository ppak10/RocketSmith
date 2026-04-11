import { useEffect } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
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
import type { WatchEvent, NavigateCommand } from "../hooks/useWatchSocket";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import type { FileNode } from "@/hooks/useFileTree";
import { FileTree } from "./FileTree";

interface DashboardProps {
  events: WatchEvent[];
  connected: boolean;
  offline: boolean;
  dark: boolean;
  onToggleTheme: () => void;
  navigation: NavigateCommand | null;
}

const NAV_ITEMS = [
  { id: "/", title: "Live", icon: Activity, requiresFile: null },
  {
    id: "/flights",
    title: "Flights",
    icon: LineChart,
    requiresFile: ".ork",
  },
  {
    id: "/assembly",
    title: "Assembly",
    icon: Box,
    requiresFile: "assembly.json",
  },
];

/** Map server panel names to router paths. */
const PANEL_TO_PATH: Record<string, string> = {
  live: "/",
  flight: "/flights",
  assembly: "/assembly",
};

/** Map router paths to display titles. */
const PATH_TITLES: Record<string, string> = {
  "/": "Live",
  "/flights": "Flights",
  "/assembly": "Assembly",
};

/** Check if a file matching a name or extension exists in the tree. */
function hasFile(tree: FileNode[], match: string): boolean {
  for (const node of tree) {
    if (node.type === "file") {
      if (match.startsWith(".") ? node.name.endsWith(match) : node.name === match) {
        return true;
      }
    }
    if (node.children && hasFile(node.children, match)) return true;
  }
  return false;
}

/** Get the router path for a file based on its extension. */
function fileToPath(filePath: string): string {
  const ext = filePath.slice(filePath.lastIndexOf(".")).toLowerCase();
  if ([".step", ".stp"].includes(ext)) return `/file/step/${filePath}`;
  if (ext === ".ork") return "/flights";
  return `/file/${filePath}`;
}

export function Dashboard({
  events,
  connected,
  offline,
  dark,
  onToggleTheme,
  navigation,
}: DashboardProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const project = useProjectInfo();
  const fileTree = useFileTree(events);

  // Handle navigation commands from the WebSocket server.
  useEffect(() => {
    if (navigation) {
      const path = PANEL_TO_PATH[navigation.panel];
      if (path) {
        navigate(path);
      } else if (navigation.file) {
        navigate(fileToPath(navigation.file));
      }
    }
  }, [navigation, navigate]);

  const currentPath = location.pathname;
  const title =
    PATH_TITLES[currentPath] ??
    (currentPath.startsWith("/file/") ? "File" : currentPath);

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
                  const disabled = item.requiresFile
                    ? !hasFile(fileTree, item.requiresFile)
                    : false;
                  const isActive =
                    item.id === "/"
                      ? currentPath === "/"
                      : currentPath.startsWith(item.id);
                  return (
                    <SidebarMenuItem key={item.id}>
                      <SidebarMenuButton
                        isActive={isActive}
                        className={
                          disabled ? "opacity-40 pointer-events-none" : ""
                        }
                        onClick={() => !disabled && navigate(item.id)}
                      >
                        <item.icon className="size-4" />
                        <span>{item.title}</span>
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
                  onSelect={(path) => navigate(fileToPath(path))}
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
          <h2 className="text-sm font-heading text-foreground">{title}</h2>
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
          <Outlet />
        </main>
      </SidebarInset>
    </TooltipProvider>
  );
}

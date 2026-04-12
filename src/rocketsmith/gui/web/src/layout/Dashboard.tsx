import { useCallback, useEffect, useMemo, useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  Moon,
  Sun,
  Rocket,
  Box,
  LineChart,
  Activity,
  Network,
} from "lucide-react";
import type { WatchEvent, NavigateCommand } from "../hooks/useWatchSocket";
import { apiBase } from "@/lib/server";
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
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { useProjectInfo } from "@/hooks/useProjectInfo";
import { useFileTree } from "@/hooks/useFileTree";
import type { FileNode } from "@/hooks/useFileTree";

interface DashboardProps {
  events: WatchEvent[];
  connected: boolean;
  offline: boolean;
  dark: boolean;
  onToggleTheme: () => void;
  navigation: NavigateCommand | null;
  clearNavigation: () => void;
}

const NAV_ITEMS = [
  { id: "/", title: "Live", icon: Activity, requiresFile: null },
  {
    id: "/component-tree",
    title: "Component Tree",
    icon: Network,
    requiresFile: "component_tree.json",
  },
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

/** Map router paths to display titles. */
const PATH_TITLES: Record<string, string> = {
  "/": "Live",
  "/flights": "Flights",
  "/component-tree": "Component Tree",
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

export function Dashboard({
  events,
  connected,
  offline,
  dark,
  onToggleTheme,
  navigation,
  clearNavigation,
}: DashboardProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const project = useProjectInfo();
  const fileTree = useFileTree(events);

  // Find part JSON files under parts/ and fetch display names.
  const partFileNodes = useMemo(() => {
    const partsNode = fileTree.find((n) => n.name === "parts" && n.type === "directory");
    if (!partsNode?.children) return [];
    return partsNode.children
      .filter((n) => n.type === "file" && n.name.endsWith(".json"))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [fileTree]);

  const [partDisplayNames, setPartDisplayNames] = useState<Record<string, string>>({});

  useEffect(() => {
    if (partFileNodes.length === 0) return;
    Promise.all(
      partFileNodes.map((pf) =>
        fetch(`${apiBase()}/api/files/${pf.path}`)
          .then((r) => (r.ok ? r.json() : null))
          .catch(() => null),
      ),
    ).then((results) => {
      const names: Record<string, string> = {};
      results.forEach((data, i) => {
        if (data?.display_name) {
          names[partFileNodes[i].path] = data.display_name;
        }
      });
      setPartDisplayNames(names);
    });
  }, [partFileNodes]);

  // Handle navigation commands from the WebSocket server.
  useEffect(() => {
    if (navigation) {
      navigate(navigation.path);
      clearNavigation();
    }
  }, [navigation, navigate, clearNavigation]);

  const currentPath = location.pathname;
  const title = useMemo(() => {
    if (PATH_TITLES[currentPath]) return PATH_TITLES[currentPath];
    if (currentPath.startsWith("/parts/")) {
      const partPath = currentPath.replace(/^\//, "");
      return partDisplayNames[partPath] ?? partPath.split("/").pop()?.replace(".json", "") ?? "Part";
    }
    return currentPath;
  }, [currentPath, partDisplayNames]);

  return (
    <>
      <Sidebar>
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" className="pointer-events-none">
                <Rocket className="size-5" />
                <span className="font-heading">RocketSmith</span>
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
                        {item.id === "/" && (
                          <span
                            className={`ml-auto inline-block size-2 rounded-full ${
                              offline
                                ? "bg-foreground/20"
                                : connected
                                  ? "bg-green-500"
                                  : "bg-red-500 animate-pulse"
                            }`}
                            title={
                              offline
                                ? "Offline"
                                : connected
                                  ? "Connected"
                                  : "Disconnected"
                            }
                          />
                        )}
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>

          {partFileNodes.length > 0 && (
            <SidebarGroup>
              <SidebarGroupLabel>Parts</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {partFileNodes.map((pf) => {
                    const partPath = `/${pf.path}`;
                    const label = partDisplayNames[pf.path] ?? pf.name.replace(/\.json$/, "");
                    return (
                      <SidebarMenuItem key={pf.path}>
                        <SidebarMenuButton
                          isActive={currentPath === partPath}
                          onClick={() => navigate(partPath)}
                        >
                          <Box className="size-4" />
                          <span>{label}</span>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    );
                  })}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          )}
        </SidebarContent>

      </Sidebar>

      <SidebarInset>
        <header className="relative flex items-center gap-2 border-b-2 border-border bg-background px-4 py-2">
          <SidebarTrigger />
          <h2 className="absolute left-1/2 -translate-x-1/2 text-sm font-heading text-foreground">{title}</h2>
          <div className="ml-auto">
            <Button variant="neutral" size="icon" className="size-7" onClick={onToggleTheme}>
              {dark ? (
                <Sun className="h-3.5 w-3.5" />
              ) : (
                <Moon className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>
        </header>

        <main className="flex-1 min-w-0 overflow-auto">
          <Outlet />
        </main>
      </SidebarInset>
    </>
  );
}

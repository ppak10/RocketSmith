import { useState } from "react";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  File,
  FileCode,
  FileImage,
  FileCog,
  Box,
} from "lucide-react";
import type { FileNode } from "@/hooks/useFileTree";
import {
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarMenuSub,
} from "@/components/ui/sidebar";

/** Filter the tree for sidebar display — hide flights/ under openrocket/. */
function filterForSidebar(nodes: FileNode[], parentPath = ""): FileNode[] {
  return nodes
    .filter((node) => {
      const top = parentPath.split("/")[0] || node.path.split("/")[0];
      // Under openrocket/, hide subdirectories (flights/).
      if (top === "openrocket" && parentPath && node.type === "directory") {
        return false;
      }
      // Under openrocket/, only show .ork files.
      if (top === "openrocket" && node.type === "file") {
        return node.name.endsWith(".ork");
      }
      // Hide root-level JSON files (assembly.json, component_tree.json)
      // — they have their own nav items.
      if (!parentPath && node.type === "file" && node.name.endsWith(".json")) {
        return false;
      }
      return true;
    })
    .map((node) => {
      if (node.children) {
        return { ...node, children: filterForSidebar(node.children, node.path) };
      }
      return node;
    })
    .filter((node) => node.type === "file" || (node.children && node.children.length > 0));
}

function getFileIcon(name: string) {
  const ext = name.slice(name.lastIndexOf(".")).toLowerCase();
  switch (ext) {
    case ".step":
    case ".stp":
      return Box;
    case ".py":
      return FileCode;
    case ".png":
    case ".jpg":
    case ".jpeg":
    case ".svg":
      return FileImage;
    case ".json":
    case ".toml":
    case ".yaml":
    case ".yml":
    case ".ini":
    case ".cfg":
      return FileCog;
    default:
      return File;
  }
}

function FileTreeNode({
  node,
  onSelect,
}: {
  node: FileNode;
  onSelect: (path: string) => void;
}) {
  const [open, setOpen] = useState(false);

  if (node.type === "directory") {
    return (
      <SidebarMenuItem>
        <SidebarMenuButton onClick={() => setOpen(!open)} className="text-xs">
          {open ? (
            <ChevronDown className="size-3" />
          ) : (
            <ChevronRight className="size-3" />
          )}
          <Folder className="size-3" />
          <span className="truncate">{node.name}</span>
        </SidebarMenuButton>
        {open && node.children && (
          <SidebarMenuSub>
            <SidebarMenu>
              {node.children.map((child) => (
                <FileTreeNode
                  key={child.path}
                  node={child}
                  onSelect={onSelect}
                />
              ))}
            </SidebarMenu>
          </SidebarMenuSub>
        )}
      </SidebarMenuItem>
    );
  }

  const Icon = getFileIcon(node.name);
  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        onClick={() => onSelect(node.path)}
        className="text-xs"
      >
        <Icon className="size-3" />
        <span className="truncate">{node.name}</span>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}

export function FileTree({
  tree,
  onSelect,
}: {
  tree: FileNode[];
  onSelect: (path: string) => void;
}) {
  if (tree.length === 0) {
    return (
      <p className="px-3 text-xs text-foreground/40">No files yet</p>
    );
  }

  const filtered = filterForSidebar(tree);

  return (
    <SidebarMenu>
      {filtered.map((node) => (
        <FileTreeNode key={node.path} node={node} onSelect={onSelect} />
      ))}
    </SidebarMenu>
  );
}

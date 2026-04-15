/**
 * Default backend server address used when the page is opened via file://.
 * Matches DEFAULT_HOST and DEFAULT_PORT in gui/mcp/server.py.
 */
const DEFAULT_SERVER = "127.0.0.1:24880";

/** Offline data bundle populated by gui/data.js <script> tag. */
interface OfflineData {
  filesTree: unknown[];
  projectInfo: { name: string; path: string };
  files: Record<string, unknown>;
}

function getOfflineData(): OfflineData {
  if (!(window as any).__OFFLINE_DATA__) {
    (window as any).__OFFLINE_DATA__ = {
      filesTree: [],
      projectInfo: { name: "", path: "" },
      files: {},
    };
  }
  return (window as any).__OFFLINE_DATA__;
}

/** True when running over file:// without a server. */
export function isFileProtocol(): boolean {
  return window.location.protocol === "file:" || window.location.host === "";
}

/**
 * Returns the URL for a project-relative file path.
 * Checks the offline bundle for base64-encoded binary files (STL) and
 * returns a blob URL. Falls back to a relative path.
 */
export function fileUrl(path: string): string {
  const entry = getOfflineData()?.files?.[path];
  if (
    entry &&
    typeof entry === "object" &&
    "__b64__" in (entry as Record<string, unknown>)
  ) {
    return base64ToBlobUrl((entry as { __b64__: string }).__b64__, path);
  }
  return `./${path}`;
}

/**
 * Check if a file is available (exists in the offline data bundle).
 */
export function hasOfflineFile(path: string): boolean {
  return getOfflineData()?.files?.[path] !== undefined;
}

/** Cache of blob URLs so we don't re-create them on every call. */
const _blobUrlCache = new Map<string, string>();

/** Convert a base64 string to a blob URL, with caching. */
function base64ToBlobUrl(b64: string, key: string): string {
  const cached = _blobUrlCache.get(key);
  if (cached) return cached;

  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  _blobUrlCache.set(key, url);
  return url;
}

/**
 * Read parsed JSON from the offline data bundle, falling back to the
 * API for files too large to be inlined (e.g. flight timeseries).
 */
export async function fetchJson<T = unknown>(path: string): Promise<T | null> {
  const value = getOfflineData()?.files?.[path];
  if (value !== undefined) return value as T;

  // Fallback: fetch from the API server (works in dev mode and when
  // the WebSocket server is running).
  if (!isFileProtocol()) {
    try {
      const base = `${window.location.protocol}//${window.location.host}`;
      const resp = await fetch(`${base}/api/files/${path}`);
      if (!resp.ok) return null;
      return (await resp.json()) as T;
    } catch {
      return null;
    }
  }

  return null;
}

/**
 * Read text content from the offline data bundle.
 * JSON values are stringified back to text.
 */
export async function fetchText(path: string): Promise<string | null> {
  const value = getOfflineData()?.files?.[path];
  if (typeof value === "string") return value;
  if (value !== undefined) return JSON.stringify(value);
  return null;
}

/** Get the file tree from the offline data bundle. */
export function getOfflineFilesTree(): unknown[] | null {
  return getOfflineData()?.filesTree ?? null;
}

/** Get the project info from the offline data bundle. */
export function getOfflineProjectInfo(): {
  name: string;
  path: string;
} | null {
  return getOfflineData()?.projectInfo ?? null;
}

/**
 * Update a file in the in-memory offline data bundle.
 * Called by the WS handler when file-change events arrive so that
 * subsequent reads via fetchJson/fetchText see fresh data.
 */
export function updateOfflineFile(
  path: string,
  content: string | null,
): void {
  if (content === null) return;
  const od = getOfflineData();

  // Invalidate cached blob URL so fileUrl() rebuilds from fresh data.
  const oldBlobUrl = _blobUrlCache.get(path);
  if (oldBlobUrl) {
    URL.revokeObjectURL(oldBlobUrl);
    _blobUrlCache.delete(path);
  }

  const ext = path.split(".").pop()?.toLowerCase();
  if (ext === "json") {
    try {
      const sanitized = content
        .replace(/\bNaN\b/g, "null")
        .replace(/\b-?Infinity\b/g, "null");
      od.files[path] = JSON.parse(sanitized);
    } catch {
      od.files[path] = content;
    }
  } else if (content.startsWith('{"__b64__"')) {
    // Binary file sent as base64 JSON wrapper (e.g. STL).
    try {
      od.files[path] = JSON.parse(content);
    } catch {
      od.files[path] = content;
    }
  } else {
    od.files[path] = content;
  }
}

/**
 * Replace the file tree in the in-memory offline data bundle.
 * Called by the WS handler when the server pushes a tree update.
 */
export function updateOfflineFilesTree(tree: unknown[]): void {
  getOfflineData().filesTree = tree;
}

/**
 * Update the project info in the in-memory offline data bundle.
 * Called by the WS handler when the server pushes a project-info event.
 */
export function updateOfflineProjectInfo(name: string, path: string): void {
  getOfflineData().projectInfo = { name, path };
}

/**
 * Fetch text content from the API server (for files too large for the offline bundle).
 * Returns null if the server is not running or the file is not found.
 */
export async function fetchTextFromApi(path: string): Promise<string | null> {
  const base = isFileProtocol()
    ? `http://${DEFAULT_SERVER}`
    : `${window.location.protocol}//${window.location.host}`;
  try {
    const resp = await fetch(`${base}/api/files/${path}`);
    if (!resp.ok) return null;
    return await resp.text();
  } catch {
    return null;
  }
}

/**
 * Returns the WebSocket URL for the watcher endpoint.
 */
export function wsUrl(): string {
  if (isFileProtocol()) {
    return `ws://${DEFAULT_SERVER}/ws`;
  }
  return `ws://${window.location.host}/ws`;
}

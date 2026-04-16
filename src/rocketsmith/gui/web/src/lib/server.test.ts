import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  fetchJson,
  isFileProtocol,
  updateOfflineFile,
  updateOfflineFilesTree,
} from "./server";

// ── helpers ───────────────────────────────────────────────────────────────────

/** Reset window.__OFFLINE_DATA__ between tests. */
function resetOfflineData(override: Record<string, unknown> = {}) {
  (window as any).__OFFLINE_DATA__ = {
    filesTree: [],
    projectInfo: { name: "", path: "" },
    files: {},
    ...override,
  };
}

/** Stub window.location.protocol and host. */
function mockLocation(protocol: string, host: string) {
  Object.defineProperty(window, "location", {
    writable: true,
    value: { protocol, host },
  });
}

// ── isFileProtocol ────────────────────────────────────────────────────────────

describe("isFileProtocol", () => {
  afterEach(() => {
    mockLocation("http:", "127.0.0.1:5173");
  });

  it("returns true for file: protocol", () => {
    mockLocation("file:", "");
    expect(isFileProtocol()).toBe(true);
  });

  it("returns true when host is empty string", () => {
    mockLocation("http:", "");
    expect(isFileProtocol()).toBe(true);
  });

  it("returns false for http protocol", () => {
    mockLocation("http:", "127.0.0.1:5173");
    expect(isFileProtocol()).toBe(false);
  });

  it("returns false for https protocol", () => {
    mockLocation("https:", "example.com");
    expect(isFileProtocol()).toBe(false);
  });
});

// ── fetchJson ─────────────────────────────────────────────────────────────────

describe("fetchJson", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    resetOfflineData();
    fetchSpy = vi.fn();
    (window as any).fetch = fetchSpy;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    mockLocation("http:", "127.0.0.1:5173");
  });

  describe("offline bundle hit", () => {
    it("returns data from bundle without fetching", async () => {
      resetOfflineData({ files: { "openrocket/flights/run1.json": { foo: 1 } } });
      const result = await fetchJson("openrocket/flights/run1.json");
      expect(result).toEqual({ foo: 1 });
      expect(fetchSpy).not.toHaveBeenCalled();
    });

    it("returns string values from bundle", async () => {
      resetOfflineData({ files: { "some/text.md": "hello" } });
      const result = await fetchJson<string>("some/text.md");
      expect(result).toBe("hello");
      expect(fetchSpy).not.toHaveBeenCalled();
    });
  });

  describe("API fallback — non-file:// (dev/server mode)", () => {
    beforeEach(() => {
      mockLocation("http:", "127.0.0.1:5173");
    });

    it("fetches from /api/files/{path} at current host", async () => {
      fetchSpy.mockResolvedValue({
        ok: true,
        json: async () => ({ altitude: 300 }),
      });
      const result = await fetchJson("openrocket/flights/run1.json");
      expect(fetchSpy).toHaveBeenCalledWith(
        "http://127.0.0.1:5173/api/files/openrocket/flights/run1.json",
      );
      expect(result).toEqual({ altitude: 300 });
    });

    it("returns null when the API responds with a non-OK status", async () => {
      fetchSpy.mockResolvedValue({ ok: false, status: 404 });
      const result = await fetchJson("openrocket/flights/missing.json");
      expect(result).toBeNull();
    });

    it("returns null when fetch throws a network error", async () => {
      fetchSpy.mockRejectedValue(new Error("network error"));
      const result = await fetchJson("openrocket/flights/run1.json");
      expect(result).toBeNull();
    });
  });

  describe("API fallback — file:// (production mode, the bug fix)", () => {
    beforeEach(() => {
      mockLocation("file:", "");
    });

    it("fetches from DEFAULT_SERVER (127.0.0.1:24880) instead of returning null", async () => {
      fetchSpy.mockResolvedValue({
        ok: true,
        json: async () => ({ altitude: 500 }),
      });
      const result = await fetchJson("openrocket/flights/bigfile.json");
      expect(fetchSpy).toHaveBeenCalledWith(
        "http://127.0.0.1:24880/api/files/openrocket/flights/bigfile.json",
      );
      expect(result).toEqual({ altitude: 500 });
    });

    it("returns null when the backend is unreachable", async () => {
      fetchSpy.mockRejectedValue(new Error("ECONNREFUSED"));
      const result = await fetchJson("openrocket/flights/bigfile.json");
      expect(result).toBeNull();
    });

    it("returns null when the backend returns 404", async () => {
      fetchSpy.mockResolvedValue({ ok: false, status: 404 });
      const result = await fetchJson("openrocket/flights/missing.json");
      expect(result).toBeNull();
    });

    it("prefers bundle over API when file is in offline data", async () => {
      resetOfflineData({
        files: { "openrocket/flights/small.json": { apogee: 100 } },
      });
      const result = await fetchJson("openrocket/flights/small.json");
      expect(result).toEqual({ apogee: 100 });
      expect(fetchSpy).not.toHaveBeenCalled();
    });
  });
});

// ── updateOfflineFile ─────────────────────────────────────────────────────────

describe("updateOfflineFile", () => {
  beforeEach(() => resetOfflineData());

  it("parses JSON and sanitizes NaN to null", async () => {
    updateOfflineFile("openrocket/flights/run.json", '{"v":NaN}');
    const result = await fetchJson("openrocket/flights/run.json");
    expect(result).toEqual({ v: null });
  });

  it("parses JSON and sanitizes Infinity to null", async () => {
    updateOfflineFile("openrocket/flights/run.json", '{"v":Infinity}');
    const result = await fetchJson("openrocket/flights/run.json");
    expect(result).toEqual({ v: null });
  });

  it("stores valid JSON as a parsed object", async () => {
    updateOfflineFile("cadsmith/component_tree.json", '{"parts":["nose_cone"]}');
    const result = await fetchJson("cadsmith/component_tree.json");
    expect(result).toEqual({ parts: ["nose_cone"] });
  });
});

// ── updateOfflineFilesTree ────────────────────────────────────────────────────

describe("updateOfflineFilesTree", () => {
  beforeEach(() => resetOfflineData());

  it("replaces the filesTree in the bundle", () => {
    const tree = [{ name: "openrocket", type: "directory", path: "openrocket", children: [] }];
    updateOfflineFilesTree(tree);
    expect((window as any).__OFFLINE_DATA__.filesTree).toEqual(tree);
  });
});

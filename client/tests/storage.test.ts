import { expect, test } from "vitest";
import { loadWorkspace, saveWorkspace } from "@/lib/storage";
import type { WorkspaceSnapshot } from "@/lib/schemas/workspace";

test("round trips a compressed workspace through IndexedDB", async () => {
  const snapshot: WorkspaceSnapshot = {
    version: 1,
    savedAt: new Date().toISOString(),
    nodes: [
      { id: "one", position: { x: 12, y: 24 }, data: { label: "日本語 🚀" } },
    ],
    edges: [],
  };
  await saveWorkspace("test", snapshot);
  expect(await loadWorkspace("test")).toEqual(snapshot);
  expect(await loadWorkspace("missing")).toBeNull();
});

test("rejects an invalid snapshot before writing", async () => {
  await expect(
    saveWorkspace("invalid", { version: 2 } as unknown as WorkspaceSnapshot),
  ).rejects.toThrow();
  expect(await loadWorkspace("invalid")).toBeNull();
});

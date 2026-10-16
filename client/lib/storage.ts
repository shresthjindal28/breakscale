import { openDB, type DBSchema } from "idb";
import { compressToUTF16, decompressFromUTF16 } from "lz-string";
import {
  workspaceSchema,
  type WorkspaceSnapshot,
} from "@/lib/schemas/workspace";

interface WorkspaceDatabase extends DBSchema {
  workspaces: { key: string; value: string };
}

function database() {
  if (typeof indexedDB === "undefined") {
    throw new Error(
      "Workspace storage requires a browser with IndexedDB support.",
    );
  }
  return openDB<WorkspaceDatabase>("breakscale", 1, {
    upgrade(db) {
      db.createObjectStore("workspaces");
    },
  });
}

export async function saveWorkspace(id: string, snapshot: WorkspaceSnapshot) {
  const validated = workspaceSchema.parse(snapshot);
  const db = await database();
  try {
    await db.put("workspaces", compressToUTF16(JSON.stringify(validated)), id);
  } finally {
    db.close();
  }
}

export async function loadWorkspace(
  id: string,
): Promise<WorkspaceSnapshot | null> {
  const db = await database();
  try {
    const encoded = await db.get("workspaces", id);
    if (encoded === undefined) return null;
    const json = decompressFromUTF16(encoded);
    if (!json) throw new Error("Saved workspace is corrupted.");
    return workspaceSchema.parse(JSON.parse(json));
  } finally {
    db.close();
  }
}

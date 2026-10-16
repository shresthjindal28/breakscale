import type { SimulationTrace } from "@/types/simulation-trace";
import type {
  SavedSimulation,
  SavedSimulationResult,
  SavedWorkspace,
} from "@/types/simulation-history";
import type { BackendGraph } from "@/lib/simulation/graph-adapter";
const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"
).replace(/\/$/, "");
async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (typeof body.detail?.message === "string")
        detail = `${body.detail.message}${body.detail.simulation_id ? ` (run ${body.detail.simulation_id})` : ""}`;
    } catch {
      /* Retain HTTP status. */
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export const simulationHistoryApi = {
  getTrace: (id: string) =>
    apiRequest<SimulationTrace>(`/simulations/${encodeURIComponent(id)}/trace`),
  list: (workspaceId: string) =>
    apiRequest<SavedSimulation[]>(
      `/simulations?workspace_id=${encodeURIComponent(workspaceId)}`,
    ),
  get: (id: string) =>
    apiRequest<SavedSimulation>(`/simulations/${encodeURIComponent(id)}`),
  getResults: (id: string) =>
    apiRequest<SavedSimulationResult>(
      `/simulations/${encodeURIComponent(id)}/results`,
    ),
  create: (workspaceId: string, durationSeconds = 10, seed = 42) =>
    apiRequest<SavedSimulation>("/simulations", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: workspaceId,
        duration_seconds: durationSeconds,
        seed,
      }),
    }),
  delete: (id: string) =>
    apiRequest<void>(`/simulations/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
};
export const workspaceApi = {
  list: () => apiRequest<SavedWorkspace[]>("/workspaces"),
  save: (id: string | null, name: string, graph: BackendGraph) =>
    apiRequest<SavedWorkspace>(
      id ? `/workspaces/${encodeURIComponent(id)}` : "/workspaces",
      {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify({ name, graph_data: graph }),
      },
    ),
};

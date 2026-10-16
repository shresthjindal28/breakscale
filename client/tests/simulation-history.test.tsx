import { setAccessToken } from "@/lib/api/auth";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import {
  SimulationComparison,
  formatMetric,
} from "@/components/simulation/simulation-comparison";
import { SimulationHistory } from "@/components/simulation/simulation-history";
import { simulationHistoryApi } from "@/lib/api/simulation-history";
import type { SavedSimulation } from "@/types/simulation-history";

afterEach(() => vi.unstubAllGlobals());
test("older saved runs display missing values rather than zero", () => {
  render(
    <SimulationComparison
      first={{ simulation_id: "a", summary: {}, node_metrics: {} }}
      second={{
        simulation_id: "b",
        summary: { throughput_rps: 20 },
        node_metrics: {},
      }}
    />,
  );
  const row = screen.getByText("Throughput").closest("tr")!;
  expect(within(row).getAllByText("N/A")).toHaveLength(2);
  expect(within(row).getByText("20.00 RPS")).toBeInTheDocument();
  expect(formatMetric(Number.NaN)).toBe("N/A");
});
test("comparison highlights improvement and percent differences", () => {
  render(
    <SimulationComparison
      first={{
        simulation_id: "a",
        summary: { throughput_rps: 10, error_rate: 0.2 },
        node_metrics: {},
      }}
      second={{
        simulation_id: "b",
        summary: { throughput_rps: 20, error_rate: 0.1 },
        node_metrics: {},
      }}
    />,
  );
  expect(screen.getByText("+10.00 RPS")).toHaveClass("text-emerald-600");
  expect(screen.getByText("-10.00%")).toHaveClass("text-emerald-600");
});
test("selection is limited to two completed runs and delete errors surface", async () => {
  const runs: SavedSimulation[] = ["a", "b", "c", "d"].map((id, i) => ({
    id,
    workspace_id: "w",
    status: i === 3 ? "failed" : "completed",
    duration_seconds: 10,
    created_at: null,
    graph_snapshot: null,
  }));
  const compare = vi.fn();
  render(
    <SimulationHistory
      runs={runs}
      loading={false}
      onCompare={compare}
      onDelete={async () => {
        throw new Error("Delete failed");
      }}
    />,
  );
  fireEvent.click(screen.getByLabelText("Select simulation a"));
  fireEvent.click(screen.getByLabelText("Select simulation b"));
  fireEvent.click(screen.getByLabelText("Select simulation c"));
  expect(screen.getByLabelText("Select simulation a")).not.toBeChecked();
  expect(screen.getByLabelText("Select simulation d")).toBeDisabled();
  fireEvent.click(screen.getByText("Compare Selected"));
  expect(compare).toHaveBeenCalledWith("b", "c");
  fireEvent.click(screen.getByLabelText("Delete simulation a"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Delete failed");
});
test("delete API accepts 204 and structured errors preserve run ID", async () => {
  setAccessToken("test-token");
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(new Response(null, { status: 204 }))
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: { message: "Simulation failed", simulation_id: "failed-run" },
        }),
        { status: 422 },
      ),
    );
  vi.stubGlobal("fetch", fetcher);
  await expect(simulationHistoryApi.delete("run")).resolves.toBeUndefined();
  await expect(simulationHistoryApi.create("workspace")).rejects.toThrow(
    "failed-run",
  );
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
});

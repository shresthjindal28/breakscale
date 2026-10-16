import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { NodeForm } from "@/components/node-form";

test("rejects blank labels and submits trimmed labels", async () => {
  const onAdd = vi.fn();
  render(<NodeForm onAdd={onAdd} />);
  fireEvent.click(screen.getByRole("button", { name: "Add node" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Enter a label");
  expect(onAdd).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Node label"), {
    target: { value: "  Research  " },
  });
  fireEvent.click(screen.getByRole("button", { name: "Add node" }));
  await waitFor(() =>
    expect(onAdd).toHaveBeenCalledWith("Research", "service"),
  );
  await waitFor(() =>
    expect(screen.getByLabelText("Node label")).toHaveValue(""),
  );
});

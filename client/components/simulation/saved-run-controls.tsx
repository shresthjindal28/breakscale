"use client";
import { useState } from "react";
import { Database, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
export function SavedRunControls({
  disabled,
  saving,
  onRun,
}: {
  disabled: boolean;
  saving: boolean;
  onRun: (duration: number) => Promise<void>;
}) {
  const [duration, setDuration] = useState(10);
  return (
    <div className="flex flex-wrap items-center gap-3">
      <label className="text-sm">
        Saved run duration{" "}
        <select
          aria-label="Saved run duration"
          value={duration}
          onChange={(event) => setDuration(Number(event.target.value))}
          disabled={saving}
          className="rounded-md border bg-background px-3 py-2"
        >
          {[5, 10, 30, 60].map((value) => (
            <option key={value} value={value}>
              {value} seconds
            </option>
          ))}
        </select>
      </label>
      <Button
        disabled={disabled || saving}
        onClick={() => void onRun(duration)}
      >
        {saving ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Database className="size-4" />
        )}
        Save & Run
      </Button>
    </div>
  );
}

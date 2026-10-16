"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { nodeFormSchema, type NodeFormValues } from "@/lib/schemas/workspace";

export function NodeForm({ onAdd }: { onAdd: (label: string) => void }) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<NodeFormValues>({
    resolver: zodResolver(nodeFormSchema),
    defaultValues: { label: "" },
  });
  return (
    <form
      className="space-y-3"
      onSubmit={handleSubmit(({ label }) => {
        onAdd(label);
        reset();
      })}
    >
      <Label htmlFor="node-label">Node label</Label>
      <Input
        id="node-label"
        {...register("label")}
        aria-invalid={!!errors.label}
        aria-describedby={errors.label ? "label-error" : undefined}
      />
      {errors.label && (
        <p id="label-error" role="alert" className="text-sm text-destructive">
          {errors.label.message}
        </p>
      )}
      <Button type="submit">
        <Plus aria-hidden="true" />
        Add node
      </Button>
    </form>
  );
}

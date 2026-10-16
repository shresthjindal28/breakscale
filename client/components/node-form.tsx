"use client";

import { useState } from "react";
import {
  COMPONENT_TYPES,
  type ComponentType,
} from "@/lib/simulation/graph-adapter";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { nodeFormSchema, type NodeFormValues } from "@/lib/schemas/workspace";

export function NodeForm({
  onAdd,
}: {
  onAdd: (label: string, componentType: ComponentType) => void;
}) {
  const [componentType, setComponentType] = useState<ComponentType>("service");
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
        onAdd(label, componentType);
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
      <Label htmlFor="component-type">Component type</Label>
      <select
        id="component-type"
        value={componentType}
        onChange={(event) =>
          setComponentType(event.target.value as ComponentType)
        }
        className="w-full rounded-md border bg-background px-3 py-2 text-sm"
      >
        {COMPONENT_TYPES.map((type) => (
          <option key={type} value={type}>
            {type === "loadBalancer"
              ? "Load balancer"
              : type.charAt(0).toUpperCase() + type.slice(1)}
          </option>
        ))}
      </select>
      <Button type="submit">
        <Plus aria-hidden="true" />
        Add node
      </Button>
    </form>
  );
}

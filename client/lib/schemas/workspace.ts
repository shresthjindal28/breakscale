import { z } from "zod";

export const nodeFormSchema = z.object({
  label: z
    .string()
    .trim()
    .min(1, "Enter a label")
    .max(80, "Use 80 characters or fewer"),
});

export const workspaceSchema = z.object({
  version: z.literal(1),
  savedAt: z.string().datetime(),
  nodes: z.array(
    z.object({
      id: z.string(),
      position: z.object({ x: z.number(), y: z.number() }),
      data: nodeFormSchema,
    }),
  ),
  edges: z.array(
    z.object({ id: z.string(), source: z.string(), target: z.string() }),
  ),
});

export type NodeFormValues = z.infer<typeof nodeFormSchema>;
export type WorkspaceSnapshot = z.infer<typeof workspaceSchema>;

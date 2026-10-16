import { AuthGate } from "@/components/auth/auth-gate";
import type { Metadata } from "next";
import { WorkspacePlayground } from "@/components/workspace-playground";

export const metadata: Metadata = {
  title: "Workspace playground | Breakscale",
};

export default function PlaygroundPage() {
  return (
    <AuthGate>
      <WorkspacePlayground />
    </AuthGate>
  );
}

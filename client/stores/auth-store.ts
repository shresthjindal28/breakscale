"use client";
import { create } from "zustand";
import {
  currentUser,
  login,
  register,
  logout,
  refreshAccessToken,
  type AuthUser,
} from "@/lib/api/auth";
import { useSimulationStore } from "@/stores/simulation-store";
import { usePlaybackStore } from "@/stores/playback-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
interface AuthState {
  user: AuthUser | null;
  status: "loading" | "authenticated" | "anonymous";
  restore: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}
let restoring: Promise<void> | null = null;
export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  status: "loading",
  restore: async () => {
    if (get().status !== "loading") return;
    if (!restoring)
      restoring = (async () => {
        try {
          await refreshAccessToken();
          set({ user: await currentUser(), status: "authenticated" });
        } catch {
          set({ user: null, status: "anonymous" });
        }
      })().finally(() => {
        restoring = null;
      });
    return restoring;
  },
  signIn: async (email, password) => {
    await login(email, password);
    set({ user: await currentUser(), status: "authenticated" });
  },
  signUp: async (name, email, password) => {
    await register(name, email, password);
    set({ user: await currentUser(), status: "authenticated" });
  },
  signOut: async () => {
    await logout();
    useSimulationStore.getState().reset();
    usePlaybackStore.getState().reset();
    useWorkspaceStore.setState({ nodes: [], edges: [] });
    set({ user: null, status: "anonymous" });
  },
}));

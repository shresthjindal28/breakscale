"use client";
import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth-store";
export function AuthGate({ children }: { children: ReactNode }) {
  const { user, status, restore, signOut } = useAuthStore();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    void restore();
  }, [restore]);
  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);
  if (status !== "authenticated" || !user)
    return <main className="p-8">Checking session...</main>;
  return (
    <div key={user.id}>
      <nav className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-3">
        <div className="flex gap-4">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/playground">Playground</Link>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm">{user.name || user.email}</span>
          <Button
            variant="outline"
            onClick={() => {
              void signOut().catch((err) => setError(err.message));
            }}
          >
            Sign out
          </Button>
        </div>
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
      </nav>
      {children}
    </div>
  );
}

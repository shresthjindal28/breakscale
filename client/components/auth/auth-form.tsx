"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthStore } from "@/stores/auth-store";
export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const { signIn, signUp } = useAuthStore();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <main className="mx-auto w-full max-w-md space-y-5 p-8">
      <h1 className="text-2xl font-semibold">
        {mode === "login"
          ? "Sign in to Breakscale"
          : "Create your Breakscale account"}
      </h1>
      <form
        className="space-y-4"
        onSubmit={async (event) => {
          event.preventDefault();
          setError(null);
          const form = new FormData(event.currentTarget);
          const parsed = z
            .object({
              email: z.string().email(),
              password: z
                .string()
                .min(mode === "register" ? 12 : 1)
                .max(128),
              name: z
                .string()
                .trim()
                .min(mode === "register" ? 1 : 0)
                .max(100),
            })
            .safeParse({
              email: form.get("email"),
              password: form.get("password"),
              name: form.get("name") ?? "",
            });
          if (!parsed.success) {
            setError(parsed.error.issues[0]?.message ?? "Check your details");
            return;
          }
          setBusy(true);
          try {
            if (mode === "register")
              await signUp(
                parsed.data.name,
                parsed.data.email,
                parsed.data.password,
              );
            else await signIn(parsed.data.email, parsed.data.password);
            router.replace("/dashboard");
          } catch (err) {
            setError(
              err instanceof Error ? err.message : "Authentication failed",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        {mode === "register" && (
          <div className="space-y-2">
            <Label htmlFor="auth-name">Name</Label>
            <Input
              id="auth-name"
              name="name"
              autoComplete="name"
              required
              maxLength={100}
            />
          </div>
        )}
        <div className="space-y-2">
          <Label htmlFor="auth-email">Email</Label>
          <Input
            id="auth-email"
            name="email"
            type="email"
            autoComplete="email"
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="auth-password">Password</Label>
          <Input
            id="auth-password"
            name="password"
            type="password"
            autoComplete={
              mode === "login" ? "current-password" : "new-password"
            }
            minLength={mode === "register" ? 12 : 1}
            maxLength={128}
            required
          />
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" disabled={busy}>
          {busy
            ? "Please wait..."
            : mode === "login"
              ? "Sign in"
              : "Create account"}
        </Button>
      </form>
      <Link
        className="text-sm underline"
        href={mode === "login" ? "/register" : "/login"}
      >
        {mode === "login" ? "Create an account" : "Already registered? Sign in"}
      </Link>
    </main>
  );
}

import Link from "next/link";
import { AuthGate } from "@/components/auth/auth-gate";
export default function Dashboard() {
  return (
    <AuthGate>
      <main className="mx-auto max-w-4xl space-y-4 p-8">
        <h1 className="text-3xl font-semibold">Your simulation workspace</h1>
        <p>
          Build architectures, run simulations, compare saved runs, and replay
          recorded requests.
        </p>
        <Link
          className="inline-block rounded-md bg-primary px-4 py-2 text-primary-foreground"
          href="/playground"
        >
          Open playground
        </Link>
      </main>
    </AuthGate>
  );
}

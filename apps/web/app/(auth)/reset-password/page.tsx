"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { confirmPasswordResetAction } from "./actions";

/**
 * The reset link is `{web_url}/reset-password#<token>` -- the token lives in
 * the URL fragment, which browsers never send to any server, so uvicorn's
 * access log never sees it. That only holds if this page reads the fragment
 * itself: a Server Component cannot see it at all, so this has to be a
 * client component, and the token has to stay out of every link and every
 * rendered string from here on. Same rule as app/invites/page.tsx.
 */
export default function ResetPasswordPage() {
  const router = useRouter();
  // Starts null on both the server render and the client's first
  // (hydrating) render -- neither has read the fragment yet, so they agree.
  // Reading window.location.hash during render would desync hydration.
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(() => {
      setToken(window.location.hash.slice(1) || null);
      setReady(true);
    });
  }, []);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setError(null);
    startTransition(async () => {
      const result = await confirmPasswordResetAction(token, password);
      if (result.ok) {
        // No session is minted by the reset, so this ends at sign-in.
        router.push("/login");
        return;
      }
      setError(
        result.invalid
          ? "This link is no longer valid. Ask for a new one."
          : result.message,
      );
    });
  }

  if (!ready) return null;

  if (!token) {
    return (
      <div className="w-full max-w-sm space-y-4">
        <h1 className="text-lg font-semibold text-ink-900">
          This link is not valid
        </h1>
        <p className="text-sm text-ink-600">
          It may have expired or already been used.
        </p>
        <Link
          href="/forgot-password"
          className="inline-block text-sm font-medium text-ink-900 underline underline-offset-4"
        >
          Ask for a new link
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="w-full max-w-sm space-y-4">
      <h1 className="text-lg font-semibold text-ink-900">Choose a new password</h1>
      {error ? (
        <p
          role="alert"
          className="rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-[13px] text-danger-700"
        >
          {error}
        </p>
      ) : null}
      <div className="space-y-2">
        <Label htmlFor="password" className="text-sm">
          New password
        </Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <p className="text-xs text-ink-500">At least 8 characters.</p>
      </div>
      <Button type="submit" variant="primary" size="lg" className="w-full" disabled={isPending}>
        {isPending ? "Saving…" : "Save and sign in"}
      </Button>
    </form>
  );
}

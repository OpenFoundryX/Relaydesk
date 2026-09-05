"use client";

import { useEffect, useState, useTransition, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import type { InvitePreview } from "@/lib/api/invites";

import { acceptInviteAction, previewInviteAction } from "./actions";

type Status = "loading" | "invalid" | "ready";

/**
 * The invite link is `{web_url}/invites#<token>` -- the token lives in the
 * URL fragment, which browsers never send to any server, so uvicorn's
 * access log (on by default, no config here disables it) never sees it.
 * That only holds if this page reads the fragment itself: a Server
 * Component cannot see it at all, so this has to be a client component,
 * and the token has to stay out of every link and every rendered string
 * from here on.
 */
export default function InvitePage() {
  const router = useRouter();
  // Starts as "loading" on both the server render and the client's first
  // (hydrating) render -- neither has read the fragment yet, so they agree.
  // Reading `window.location.hash` has to wait for the effect below: doing
  // it during render would make the server's guess (no window, so "no
  // token") diverge from the client's real answer and desync hydration.
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [invite, setInvite] = useState<InvitePreview | null>(null);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    const fragment = window.location.hash.slice(1) || null;
    startTransition(async () => {
      if (!fragment) {
        setStatus("invalid");
        return;
      }
      setToken(fragment);
      const result = await previewInviteAction(fragment);
      if (result.ok) {
        setInvite(result.invite);
        setStatus("ready");
      } else {
        setStatus("invalid");
      }
    });
  }, []);

  function submit() {
    if (!token) return;
    setError(null);
    startTransition(async () => {
      const result = await acceptInviteAction(token, name.trim(), password);
      if (result.ok) {
        router.push("/conversations?status=open");
        return;
      }
      if (result.invalid) {
        setStatus("invalid");
        return;
      }
      setError(result.message);
    });
  }

  if (status === "loading") {
    return (
      <Card>
        <p className="text-[13px] text-ink-500">Checking your invitation…</p>
      </Card>
    );
  }

  if (status === "invalid") {
    return (
      <Card>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-950">
          This invitation is no longer valid
        </h1>
        <p className="mt-2 text-[13px] text-ink-500">
          The link may have expired, been revoked, or already been used. Ask a workspace
          admin for a new one.
        </p>
        <Button asChild variant="primary" size="lg" className="mt-6 w-full">
          <Link href="/login">Go to sign in</Link>
        </Button>
      </Card>
    );
  }

  if (!invite) return null;

  return (
    <Card>
      <h1 className="text-2xl font-semibold tracking-tight text-ink-950">
        Join {invite.workspaceName}
      </h1>
      <p className="mt-2 text-[13px] text-ink-500">
        You&apos;ve been invited as {invite.role === "Admin" ? "an admin" : "an agent"}. Set
        up your account for{" "}
        <span className="font-medium text-ink-900">{invite.email}</span>.
      </p>

      {error ? (
        <p
          role="alert"
          className="mt-6 rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-[13px] text-danger-700"
        >
          {error}
        </p>
      ) : null}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
        className="mt-6 space-y-5"
      >
        <div className="space-y-2">
          <Label htmlFor="name" className="text-sm">
            Full name
          </Label>
          <Input
            id="name"
            name="name"
            type="text"
            autoComplete="name"
            placeholder="Jane Alvarez"
            className="h-10"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password" className="text-sm">
            Password
          </Label>
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete="new-password"
            className="h-10"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>
        <Button type="submit" variant="primary" size="lg" className="mt-2 w-full" disabled={isPending}>
          {isPending ? "Setting up…" : "Accept invite"}
        </Button>
      </form>

      <p className="mt-8 text-[13px] text-ink-500">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-ink-900 underline underline-offset-4">
          Sign in
        </Link>
      </p>
    </Card>
  );
}

function Card({ children }: { children: ReactNode }) {
  return (
    <div className="w-full max-w-md rounded-xl border border-ink-200 bg-white px-8 py-12 shadow-overlay sm:px-12">
      {children}
    </div>
  );
}

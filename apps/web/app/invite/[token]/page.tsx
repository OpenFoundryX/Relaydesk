import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import { getInvitePreview, type InvitePreview } from "@/lib/api/invites";

import { accept } from "./actions";

export const metadata: Metadata = { title: "Accept your invite" };

const SUBMIT_ERRORS: Record<string, string> = {
  fields: "Enter your name and choose a password.",
  "404": "This invite is no longer valid. Ask an admin to send a new one.",
  "409":
    "This address already belongs to a Relaydesk workspace. Sign in with that account instead.",
};

export default async function InvitePage({
  params,
  searchParams,
}: {
  params: Promise<{ token: string }>;
  searchParams: Promise<{ error?: string }>;
}) {
  const { token } = await params;
  const { error } = await searchParams;

  let invite: InvitePreview;
  try {
    invite = await getInvitePreview(token);
  } catch (caught) {
    if (caught instanceof ApiError) return <InviteUnavailable status={caught.status} />;
    throw caught;
  }

  const message = error
    ? (SUBMIT_ERRORS[error] ?? "Something went wrong. Please try again.")
    : null;

  return (
    <Card>
      <h1 className="text-2xl font-semibold tracking-tight text-ink-950">
        Join {invite.workspaceName}
      </h1>
      <p className="mt-2 text-[13px] text-ink-500">
        You&apos;ve been invited as {invite.role === "Admin" ? "an admin" : "an agent"}.
        Set up your account for{" "}
        <span className="font-medium text-ink-900">{invite.email}</span>.
      </p>

      {message ? (
        <p
          role="alert"
          className="mt-6 rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-[13px] text-danger-700"
        >
          {message}
        </p>
      ) : null}

      <form action={accept} className="mt-6 space-y-5">
        <input type="hidden" name="token" value={token} />
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
            required
          />
        </div>
        <Button type="submit" variant="primary" size="lg" className="mt-2 w-full">
          Accept invite
        </Button>
      </form>

      <p className="mt-8 text-[13px] text-ink-500">
        Already have an account?{" "}
        <Link
          href="/login"
          className="font-medium text-ink-900 underline underline-offset-4"
        >
          Sign in
        </Link>
      </p>
    </Card>
  );
}

/**
 * A used-up or expired link is an ordinary outcome, not a crash: say so
 * plainly and point at sign-in rather than letting the error boundary take
 * the screen.
 */
function InviteUnavailable({ status }: { status: number }) {
  const accepted = status === 409;
  return (
    <Card>
      <h1 className="text-2xl font-semibold tracking-tight text-ink-950">
        {accepted
          ? "This invite has already been used"
          : "This invite isn’t valid"}
      </h1>
      <p className="mt-2 text-[13px] text-ink-500">
        {accepted
          ? "Someone has already accepted it. Sign in with the account it created."
          : "The link may have expired, been revoked, or been copied incompletely. Ask a workspace admin to send you a new one."}
      </p>
      <Button asChild variant="primary" size="lg" className="mt-6 w-full">
        <Link href="/login">Go to sign in</Link>
      </Button>
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

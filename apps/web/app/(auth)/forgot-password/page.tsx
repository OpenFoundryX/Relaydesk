"use client";

import { useState, useTransition } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { requestPasswordResetAction } from "./actions";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [isPending, startTransition] = useTransition();

  function submit(event: React.FormEvent) {
    event.preventDefault();
    startTransition(async () => {
      await requestPasswordResetAction(email.trim());
      // Shown whatever the address was. See the action's comment.
      setSent(true);
    });
  }

  if (sent) {
    return (
      <div className="w-full max-w-sm space-y-4">
        <h1 className="text-lg font-semibold text-ink-900">Check your email</h1>
        <p className="text-sm text-ink-600">
          If that address has a Relaydesk account with a password, we have sent
          it a link to choose a new one. The link expires in an hour.
        </p>
        <Link
          href="/login"
          className="inline-block text-sm font-medium text-ink-900 underline underline-offset-4"
        >
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="w-full max-w-sm space-y-4">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold text-ink-900">Reset your password</h1>
        <p className="text-sm text-ink-600">
          We will email you a link to choose a new one.
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="email" className="text-sm">
          Email
        </Label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <Button type="submit" variant="primary" size="lg" className="w-full" disabled={isPending}>
        {isPending ? "Sending…" : "Send the link"}
      </Button>
      <Link
        href="/login"
        className="block text-sm font-medium text-ink-900 underline underline-offset-4"
      >
        Back to sign in
      </Link>
    </form>
  );
}

import type { Metadata } from "next";
import Link from "next/link";

import { InboxPreview } from "@/components/marketing/inbox-preview";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { signIn, signInWithGoogle } from "./actions";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; expired?: string }>;
}) {
  const { error, expired } = await searchParams;

  return (
    <div className="grid w-full max-w-5xl overflow-hidden rounded-xl border border-ink-200 bg-white shadow-overlay lg:min-h-[600px] lg:grid-cols-[minmax(0,26rem)_1fr]">
      <div className="px-8 py-12 sm:px-12 lg:py-20">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-950">Sign in</h1>

        <form action={signInWithGoogle} className="mt-6">
          <Button type="submit" variant="secondary" size="lg" className="w-full">
            <GoogleMark />
            Continue with Google
          </Button>
        </form>

        <div className="my-6 flex items-center gap-3 text-[13px] text-ink-500">
          <span className="h-px flex-1 bg-ink-200" />
          Or continue with email
          <span className="h-px flex-1 bg-ink-200" />
        </div>

        {error === "google" ? (
          <p
            role="alert"
            className="mb-4 rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-[13px] text-danger-700"
          >
            Google sign-in was cancelled or failed. Please try again.
          </p>
        ) : error ? (
          <p
            role="alert"
            className="mb-4 rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-[13px] text-danger-700"
          >
            Email or password is incorrect.
          </p>
        ) : null}

        {expired ? (
          <p
            role="alert"
            className="mb-4 rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-[13px] text-danger-700"
          >
            Your session has expired. Please sign in again.
          </p>
        ) : null}

        <form action={signIn} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="email" className="text-sm">
              Email
            </Label>
            <Input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="jane@acme.com"
              className="h-10"
              required
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="password" className="text-sm">
                Password
              </Label>
              <Link
                href="/forgot-password"
                className="text-[13px] text-ink-500 underline-offset-4 hover:text-ink-900 hover:underline"
              >
                Forgot password?
              </Link>
            </div>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              className="h-10"
              required
            />
          </div>
          <Button type="submit" variant="primary" size="lg" className="mt-2 w-full">
            Sign in
          </Button>
        </form>

        <p className="mt-8 text-[13px] text-ink-500">
          Don&apos;t have an account?{" "}
          <Link href="/contact" className="font-medium text-ink-900 underline underline-offset-4">
            Contact us
          </Link>
        </p>
      </div>

      {/* Product preview, bleeding off the card's right edge. */}
      <div className="relative hidden lg:block" aria-hidden>
        <div className="absolute left-10 top-1/2 w-[46rem] -translate-y-1/2">
          <InboxPreview className="rounded-r-none border-r-0" />
        </div>
      </div>
    </div>
  );
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 24 24" className="size-4" aria-hidden>
      <path fill="#4285F4" d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47a5.53 5.53 0 0 1-2.4 3.63v3h3.87c2.27-2.09 3.55-5.17 3.55-8.87z" />
      <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.94-2.91l-3.87-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09A12 12 0 0 0 12 24z" />
      <path fill="#FBBC05" d="M5.27 14.29A7.2 7.2 0 0 1 4.9 12c0-.8.14-1.57.37-2.29V6.62H1.29A12 12 0 0 0 0 12c0 1.94.46 3.77 1.29 5.38l3.98-3.09z" />
      <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0A12 12 0 0 0 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75z" />
    </svg>
  );
}

"use client";

import { useState, type FormEvent } from "react";
import { ArrowLeft } from "lucide-react";

import { WidgetButton } from "@/components/widget/button";
import type { SubmitWidgetTicketResult } from "@/app/(widget)/widget/frame/actions";

type Status = "idle" | "submitting" | "failed";

/**
 * The message form. Reached from Home (secondary), Results or Article
 * (primary), or is the entire panel when the knowledge base is empty
 * (spec D7) -- `showBack` is false only in that last case, since there is
 * nowhere behind it to go back to.
 *
 * `onSubmit` arrives as a prop -- the server action itself, bound to this
 * embed's key by the frame page -- rather than being imported here. A
 * Client Component may take a Server Action as a prop and call it exactly
 * like this; it must not import the module that defines one, because that
 * module also imports `lib/api/widget.ts`, which is `server-only`. Next's
 * real build strips that chain out of the client bundle for a statically
 * imported action; nothing here relies on that -- the prop boundary keeps
 * it out of the client graph regardless of which bundler is watching.
 */
export function Compose({
  showBack,
  onBack,
  onSent,
  onSubmit,
}: {
  showBack: boolean;
  onBack: () => void;
  onSent: () => void;
  onSubmit?: (formData: FormData) => Promise<SubmitWidgetTicketResult>;
}) {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");

  const canSubmit = email.includes("@") && message.trim().length > 0;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!onSubmit) {
      setStatus("failed");
      setError("This widget is not configured correctly.");
      return;
    }
    setStatus("submitting");
    setError(null);

    try {
      const result = await onSubmit(new FormData(event.currentTarget));
      if (result.ok) {
        onSent();
      } else {
        setStatus("failed");
        setError(result.message);
      }
    } catch {
      setStatus("failed");
      setError("We couldn't reach the server. Please try again.");
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-4 px-4 py-6">
      {showBack && (
        <button
          type="button"
          onClick={onBack}
          className="-mt-1 flex w-fit items-center gap-1.5 text-[12px] text-ink-500 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:text-ink-400 dark:hover:text-white"
        >
          <ArrowLeft className="size-3.5" aria-hidden />
          Back
        </button>
      )}

      <h1 className="text-[15px] font-semibold tracking-tight text-ink-900 dark:text-white">
        Send us a message
      </h1>

      <form className="flex flex-1 flex-col gap-3" onSubmit={handleSubmit}>
        {status === "failed" && error && (
          <p role="alert" className="text-[12px] text-danger-700 dark:text-danger-200">
            {error}
          </p>
        )}

        <div className="flex flex-col gap-1">
          <label htmlFor="widget-email" className="text-[12px] font-medium text-ink-700 dark:text-ink-300">
            Email
          </label>
          <input
            id="widget-email"
            name="email"
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            className="h-9 rounded-md border border-ink-200 bg-white px-3 text-[13px] text-ink-900 placeholder:text-ink-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:border-ink-700 dark:bg-ink-800 dark:text-white"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="widget-name" className="text-[12px] font-medium text-ink-700 dark:text-ink-300">
            Name
          </label>
          <input
            id="widget-name"
            name="name"
            placeholder="Your name (optional)"
            className="h-9 rounded-md border border-ink-200 bg-white px-3 text-[13px] text-ink-900 placeholder:text-ink-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:border-ink-700 dark:bg-ink-800 dark:text-white"
          />
        </div>

        <div className="flex flex-1 flex-col gap-1">
          <label htmlFor="widget-message" className="text-[12px] font-medium text-ink-700 dark:text-ink-300">
            Your message
          </label>
          <textarea
            id="widget-message"
            name="message"
            required
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="What's going on?"
            className="min-h-24 flex-1 resize-none rounded-md border border-ink-200 bg-white px-3 py-2 text-[13px] text-ink-900 placeholder:text-ink-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:border-ink-700 dark:bg-ink-800 dark:text-white"
          />
        </div>

        {/* The honeypot -- hidden with CSS, not `type="hidden"`, and kept
            out of tab order and screen-reader reach, exactly as the
            portal's form does it. The API answers a filled one with the
            same 201 a real submission gets. */}
        <div
          aria-hidden="true"
          style={{ position: "absolute", left: "-9999px", width: 1, height: 1, overflow: "hidden" }}
        >
          <label htmlFor="widget-company">Company</label>
          <input id="widget-company" name="company" type="text" tabIndex={-1} autoComplete="off" />
        </div>

        <WidgetButton
          type="submit"
          variant="primary"
          disabled={!canSubmit || status === "submitting"}
        >
          {status === "submitting" ? "Sending…" : "Send"}
        </WidgetButton>
      </form>
    </div>
  );
}

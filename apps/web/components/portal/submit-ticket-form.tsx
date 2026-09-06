"use client";

import { useState, type FormEvent } from "react";
import { CircleCheck, Paperclip, TriangleAlert, X } from "lucide-react";

import { submitTicketAction } from "@/app/(portal)/submit-ticket/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const MAX_MESSAGE = 10_000;

type Status = "idle" | "submitting" | "submitted" | "failed";

export function SubmitTicketForm({ workspaceName }: { workspaceName: string }) {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);

  const canSubmit = email.includes("@") && message.trim().length > 0;

  function reset() {
    setStatus("idle");
    setError(null);
    setEmail("");
    setMessage("");
    setAttachments([]);
  }

  if (status === "submitted") {
    return (
      <div className="rounded-lg border border-ink-200 p-6">
        <CircleCheck className="size-6 text-accent-800" />
        <h2 className="mt-3 text-[15px] font-semibold tracking-tight text-ink-900">
          Ticket received
        </h2>
        <p className="mt-1 text-[13px] leading-relaxed text-ink-500">
          We have sent a confirmation to {email}. Replies to that thread land
          straight back with the {workspaceName} team.
        </p>
        <Button variant="secondary" size="sm" className="mt-4" onClick={reset}>
          Submit another
        </Button>
      </div>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("submitting");
    setError(null);

    const result = await submitTicketAction(new FormData(event.currentTarget));

    if (result.ok) {
      setStatus("submitted");
    } else {
      // A failed submission must never land on the success panel above --
      // that silent-looking-like-success is the exact bug this form
      // exists to not have. Stay on the form, with the reason on screen.
      setStatus("failed");
      setError(result.message);
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      {status === "failed" && error && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-danger-200 bg-danger-50 p-3 text-[13px] text-danger-700"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          <p>{error}</p>
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="email">
          Email <span className="text-danger-600">*</span>
        </Label>
        <Input
          id="email"
          name="email"
          type="email"
          required
          placeholder="you@example.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="name">Name</Label>
        <Input id="name" name="name" placeholder="Your name (optional)" />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="subject">Subject</Label>
        <Input id="subject" name="subject" placeholder="A one-line summary (optional)" />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="message">
          Message <span className="text-danger-600">*</span>
        </Label>
        <Textarea
          id="message"
          name="message"
          required
          placeholder="Describe your issue or question…"
          className="min-h-32"
          maxLength={MAX_MESSAGE}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />
        <p className="tabular text-right text-[11px] text-ink-400">
          {message.length.toLocaleString()} / {MAX_MESSAGE.toLocaleString()}
        </p>
      </div>

      {/*
       * The honeypot. Hidden with CSS, not `type="hidden"` -- a hidden
       * input is trivially skipped by a script that checks the input type
       * before filling it; one that is merely styled off-screen still
       * looks fillable to something scanning the DOM for form fields.
       * `aria-hidden` and `tabIndex={-1}` keep a screen reader or keyboard
       * user from ever landing on it, so filling it stays a bot-only
       * signal. The API answers a filled honeypot with the same 201 a
       * real submission gets -- see submit-ticket/actions.ts.
       */}
      <div
        aria-hidden="true"
        style={{ position: "absolute", left: "-9999px", top: "auto", width: 1, height: 1, overflow: "hidden" }}
      >
        <label htmlFor="company">Company</label>
        <input id="company" name="company" type="text" tabIndex={-1} autoComplete="off" />
      </div>

      <div className="space-y-1.5">
        <Label>Attachments</Label>
        {attachments.length > 0 && (
          <ul className="space-y-1">
            {attachments.map((file) => (
              <li
                key={file}
                className="flex items-center gap-2 rounded-md border border-ink-200 px-2.5 py-1.5 text-[13px] text-ink-700"
              >
                <Paperclip className="size-3.5 text-ink-400" />
                {file}
                <button
                  type="button"
                  aria-label={`Remove ${file}`}
                  onClick={() =>
                    setAttachments((current) =>
                      current.filter((entry) => entry !== file),
                    )
                  }
                  className="ml-auto rounded p-0.5 text-ink-400 transition-colors hover:text-ink-900"
                >
                  <X className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
        <Button
          type="button"
          variant="secondary"
          className="w-full"
          onClick={() =>
            setAttachments((current) => [
              ...current,
              `screenshot-${current.length + 1}.png`,
            ])
          }
        >
          <Paperclip />
          Add attachment
        </Button>
        <p className="text-[12px] text-ink-500">
          Images, video, and PDF. Up to 10MB each.
        </p>
      </div>

      <Button
        type="submit"
        variant="primary"
        size="lg"
        className="w-full"
        disabled={!canSubmit || status === "submitting"}
      >
        {status === "submitting" ? "Submitting…" : "Submit ticket"}
      </Button>

      <p className="text-center text-[12px] text-ink-400">
        By submitting, you agree to share this information with {workspaceName}.
      </p>
    </form>
  );
}

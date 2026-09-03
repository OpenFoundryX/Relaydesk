"use client";

import { useState } from "react";
import { CircleCheck, Paperclip, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const MAX_MESSAGE = 10_000;

export function SubmitTicketForm({ workspaceName }: { workspaceName: string }) {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [submitted, setSubmitted] = useState(false);

  const canSubmit = email.includes("@") && message.trim().length > 0;

  if (submitted) {
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
        <Button
          variant="secondary"
          size="sm"
          className="mt-4"
          onClick={() => {
            setSubmitted(false);
            setEmail("");
            setMessage("");
            setAttachments([]);
          }}
        >
          Submit another
        </Button>
      </div>
    );
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        setSubmitted(true);
      }}
    >
      <div className="space-y-1.5">
        <Label htmlFor="email">
          Email <span className="text-danger-600">*</span>
        </Label>
        <Input
          id="email"
          type="email"
          required
          placeholder="you@example.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="name">Name</Label>
        <Input id="name" placeholder="Your name (optional)" />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="subject">Subject</Label>
        <Input id="subject" placeholder="A one-line summary (optional)" />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="message">
          Message <span className="text-danger-600">*</span>
        </Label>
        <Textarea
          id="message"
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

      <Button type="submit" variant="primary" size="lg" className="w-full" disabled={!canSubmit}>
        Submit ticket
      </Button>

      <p className="text-center text-[12px] text-ink-400">
        By submitting, you agree to share this information with {workspaceName}.
      </p>
    </form>
  );
}

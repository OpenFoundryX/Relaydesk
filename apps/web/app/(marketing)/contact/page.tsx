import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Check, ChevronDown, Mail } from "lucide-react";

import { BrandIcon } from "@/components/brand-icons";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import { sendContact } from "./actions";

export const metadata: Metadata = {
  title: "Contact us",
  description: "Tell us about your support volume and we'll set up a Relaydesk workspace with you.",
};

const steps = [
  {
    title: "We reply within one business day",
    body: "A person, not a sequence. We'll ask about your channels, volume, and what you want the AI to handle.",
  },
  {
    title: "We set up your workspace together",
    body: "A 30-minute call to connect email or Discord, import your old help desk, and write your first triage rules.",
  },
  {
    title: "14 days free, then pick a plan",
    body: "No credit card up front. If it isn't working for your team, export everything and walk away.",
  },
];

const teamSizes = ["Just me", "2–5", "6–20", "21–50", "50+"];

export default async function ContactPage({
  searchParams,
}: {
  searchParams: Promise<{ sent?: string; name?: string }>;
}) {
  const { sent, name } = await searchParams;

  return (
    <div className="mx-auto grid max-w-6xl gap-12 px-6 py-16 lg:grid-cols-[1fr_1.1fr] lg:py-24">
      <div>
        <p className="text-[12px] font-semibold uppercase tracking-wide text-accent-800">Get started</p>
        <h1 className="mt-3 text-balance text-3xl font-semibold tracking-tight text-ink-950 sm:text-4xl">
          Tell us about your support queue.
        </h1>
        <p className="mt-4 max-w-md text-[15px] leading-relaxed text-ink-600">
          Relaydesk workspaces are set up with you, not by a signup form. Send a
          note and we&apos;ll get your channels connected and triage running.
        </p>

        <ol className="mt-10 space-y-6">
          {steps.map((step, index) => (
            <li key={step.title} className="flex gap-4">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-ink-900 text-[12px] font-semibold text-accent-500">
                {index + 1}
              </span>
              <div>
                <h2 className="text-[15px] font-semibold text-ink-900">{step.title}</h2>
                <p className="mt-1 text-[13px] leading-relaxed text-ink-600">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>

        <div className="mt-10 space-y-3 border-t border-ink-200 pt-8 text-[13px] text-ink-600">
          <p className="flex items-center gap-2">
            <Mail className="size-4 text-ink-400" aria-hidden />
            Prefer email?{" "}
            <a href="mailto:hello@relaydesk.dev" className="font-medium text-ink-900 underline underline-offset-4">
              hello@relaydesk.dev
            </a>
          </p>
          <p className="flex items-center gap-2">
            <BrandIcon brand="github" className="size-4 text-ink-400" mono />
            Want to run it yourself?{" "}
            <Link href="https://github.com/openfoundry/relaydesk" className="font-medium text-ink-900 underline underline-offset-4">
              Self-host from GitHub
            </Link>
          </p>
        </div>
      </div>

      <div className="self-start rounded-xl border border-ink-200 bg-white p-6 shadow-overlay sm:p-8">
        {sent ? <Sent name={name} /> : <ContactForm />}
      </div>
    </div>
  );
}

function ContactForm() {
  return (
    <form action={sendContact} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Your name" id="name">
          <Input id="name" name="name" autoComplete="name" placeholder="Priya Natarajan" required />
        </Field>
        <Field label="Work email" id="email">
          <Input id="email" name="email" type="email" autoComplete="email" placeholder="priya@company.com" required />
        </Field>
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Company" id="company">
          <Input id="company" name="company" autoComplete="organization" placeholder="Chronon" required />
        </Field>
        <Field label="Support team size" id="teamSize">
          <div className="relative">
            <select
              id="teamSize"
              name="teamSize"
              defaultValue=""
              required
              className="flex h-9 w-full appearance-none rounded-md border border-ink-200 bg-white px-3 pr-9 text-sm text-ink-900 transition-colors hover:border-ink-300 invalid:text-ink-400"
            >
              <option value="" disabled>
                Choose one
              </option>
              {teamSizes.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-ink-400"
              aria-hidden
            />
          </div>
        </Field>
      </div>
      <Field label="What are you hoping Relaydesk will take off your plate?" id="message">
        <Textarea
          id="message"
          name="message"
          rows={5}
          placeholder="Roughly how many tickets a month, which channels they arrive on, and what you use today."
          required
        />
      </Field>
      <Button type="submit" variant="primary" size="lg" className="w-full">
        Send message
        <ArrowRight />
      </Button>
      <p className="text-center text-[12px] text-ink-400">
        We only use this to reply to you. No newsletters, no sequences.
      </p>
    </form>
  );
}

function Sent({ name }: { name?: string }) {
  return (
    <div className="flex min-h-80 flex-col items-center justify-center text-center">
      <span className="flex size-10 items-center justify-center rounded-full bg-accent-100 text-accent-950">
        <Check className="size-5" aria-hidden />
      </span>
      <h2 className="mt-4 text-xl font-semibold tracking-tight text-ink-950">
        Thanks{name ? `, ${name}` : ""}. We&apos;ll be in touch.
      </h2>
      <p className="mt-2 max-w-xs text-[13px] leading-relaxed text-ink-600">
        Expect a reply from a real person within one business day. In the
        meantime, the repo is open if you want to poke around.
      </p>
      <Button asChild variant="secondary" size="md" className="mt-6">
        <Link href="https://github.com/openfoundry/relaydesk">
          <BrandIcon brand="github" mono />
          Browse the code
        </Link>
      </Button>
    </div>
  );
}

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  );
}

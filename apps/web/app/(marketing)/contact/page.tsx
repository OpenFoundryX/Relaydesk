import type { Metadata } from "next";
import Link from "next/link";
import { Check, ChevronDown, Mail } from "lucide-react";

import { BrandIcon } from "@/components/brand-icons";
import { PillLink } from "@/components/marketing/pill";
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
    title: "Free to start, then priced on tickets",
    body: "No credit card up front, and no per-seat charge for adding your team. If it isn't working, export everything and walk away.",
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
    <div className="mx-auto grid max-w-[1200px] gap-14 px-6 pb-20 pt-28 lg:grid-cols-[1fr_1.1fr] lg:gap-16 lg:px-10 lg:pb-24 lg:pt-36">
      <div>
        <p className="text-[14px] font-normal text-ash-gray">Get started</p>
        <h1 className="mt-5 font-display text-[40px] font-normal leading-[1.2] tracking-[-0.8px] text-ink-black sm:text-heading">
          Tell us about your queue
        </h1>
        <p className="mt-6 max-w-md text-body text-slate-gray">
          Relaydesk workspaces are set up with you, not by a signup form. Send a
          note and we&apos;ll get your channels connected and triage running.
        </p>

        <ol className="mt-10 space-y-6">
          {steps.map((step, index) => (
            <li key={step.title} className="flex gap-4">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-ink-black text-[13px] font-w450 text-paper-white">
                {index + 1}
              </span>
              <div>
                <h2 className="text-[17px] font-w450 text-ink-black">{step.title}</h2>
                <p className="mt-1.5 text-caption text-slate-gray">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>

        <div className="mt-12 space-y-3 border-t border-hairline pt-8 text-caption text-slate-gray">
          <p className="flex items-center gap-2">
            <Mail className="size-4 text-smoke-gray" aria-hidden />
            Prefer email?{" "}
            <a href="mailto:hello@relaydesk.dev" className="text-ink-black underline-offset-4 hover:underline">
              hello@relaydesk.dev
            </a>
          </p>
          <p className="flex items-center gap-2">
            <BrandIcon brand="github" className="size-4 text-smoke-gray" mono />
            Want to run it yourself?{" "}
            <Link href="https://github.com/openfoundry/relaydesk" className="text-ink-black underline-offset-4 hover:underline">
              Self-host from GitHub
            </Link>
          </p>
        </div>
      </div>

      <div className="self-start rounded-card bg-mist-gray p-6 sm:p-8">
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
          <Input id="name" name="name" autoComplete="name" placeholder="Priya Natarajan" required className="h-12 rounded-input border-hairline bg-paper-white text-[16px] text-ink-black placeholder:text-smoke-gray" />
        </Field>
        <Field label="Work email" id="email">
          <Input id="email" name="email" type="email" autoComplete="email" placeholder="priya@company.com" required className="h-12 rounded-input border-hairline bg-paper-white text-[16px] text-ink-black placeholder:text-smoke-gray" />
        </Field>
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Company" id="company">
          <Input id="company" name="company" autoComplete="organization" placeholder="Chronon" required className="h-12 rounded-input border-hairline bg-paper-white text-[16px] text-ink-black placeholder:text-smoke-gray" />
        </Field>
        <Field label="Support team size" id="teamSize">
          <div className="relative">
            <select
              id="teamSize"
              name="teamSize"
              defaultValue=""
              required
              className="flex h-12 w-full appearance-none rounded-input border border-hairline bg-paper-white px-4 pr-10 text-[16px] text-ink-black transition-colors invalid:text-smoke-gray"
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
              className="pointer-events-none absolute right-4 top-1/2 size-4 -translate-y-1/2 text-smoke-gray"
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
          className="rounded-input border-hairline bg-paper-white p-4 text-[16px] text-ink-black placeholder:text-smoke-gray"
          placeholder="Roughly how many tickets a month, which channels they arrive on, and what you use today."
          required
        />
      </Field>
      <button
        type="submit"
        className="inline-flex h-12 w-full items-center justify-center rounded-full border border-ink-black bg-ink-black text-[16px] font-normal text-paper-white transition-colors hover:bg-[#2a2d31]"
      >
        Send message
      </button>
      <p className="text-center text-[14px] text-smoke-gray">
        We only use this to reply to you. No newsletters, no sequences.
      </p>
    </form>
  );
}

function Sent({ name }: { name?: string }) {
  return (
    <div className="flex min-h-80 flex-col items-center justify-center text-center">
      <span className="flex size-10 items-center justify-center rounded-full bg-ink-black text-paper-white">
        <Check className="size-5" aria-hidden />
      </span>
      <h2 className="mt-5 font-display text-heading-sm font-normal text-ink-black">
        Thanks{name ? `, ${name}` : ""}. We&apos;ll be in touch.
      </h2>
      <p className="mt-3 max-w-xs text-caption text-slate-gray">
        Expect a reply from a real person within one business day. In the
        meantime, the repo is open if you want to poke around.
      </p>
      <PillLink
        href="https://github.com/openfoundry/relaydesk"
        variant="ghost"
        className="mt-7"
      >
        Browse the code
      </PillLink>
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

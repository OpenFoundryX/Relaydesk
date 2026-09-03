"use client";

import { useState } from "react";
import { ExternalLink, Globe } from "lucide-react";

import { Label } from "@/components/ui/label";

export function PortalUrlField({
  subdomain: initial,
  domain,
}: {
  subdomain: string;
  domain: string;
}) {
  const [subdomain, setSubdomain] = useState(initial);

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between">
        <Label htmlFor="portal-subdomain">Portal URL</Label>
        <button
          type="button"
          className="rounded text-[12px] font-medium text-ink-600 underline underline-offset-2 transition-colors hover:text-ink-900"
        >
          Use a custom domain
        </button>
      </div>

      <div className="flex h-9 items-center rounded-md border border-ink-200 bg-white pl-2.5 transition-colors focus-within:border-ink-300">
        <Globe className="size-3.5 shrink-0 text-ink-400" />
        <span className="ml-2 font-mono text-[12px] text-ink-400">https://</span>
        <input
          id="portal-subdomain"
          value={subdomain}
          onChange={(event) => setSubdomain(event.target.value)}
          className="min-w-0 flex-1 bg-transparent px-1 font-mono text-[13px] text-ink-900 outline-none"
        />
        <span className="font-mono text-[12px] text-ink-400">.{domain}</span>
        <a
          href={`https://${subdomain}.${domain}`}
          target="_blank"
          rel="noreferrer"
          aria-label="Open portal"
          className="ml-2 flex h-full items-center border-l border-ink-200 px-2.5 text-ink-400 transition-colors hover:text-ink-900"
        >
          <ExternalLink className="size-3.5" />
        </a>
      </div>
    </div>
  );
}

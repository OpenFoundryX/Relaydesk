import type { ReactNode } from "react";

import { getPortalSettings } from "@/lib/mock/workspace";

/**
 * The customer-facing portal. It shares Relaydesk's tokens but none of the
 * console chrome -- in production this is served on the tenant's own subdomain.
 */
export default async function PortalLayout({ children }: { children: ReactNode }) {
  const portal = await getPortalSettings();

  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-ink-200">
        <div className="mx-auto flex h-14 max-w-2xl items-center gap-2 px-6">
          <span className="flex size-6 items-center justify-center rounded-md bg-ink-900 text-[10px] font-semibold text-white">
            {portal.name.slice(0, 2).toUpperCase()}
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-ink-900">
            {portal.name}
          </span>
          <span className="ml-auto text-[13px] text-ink-500">Support</span>
        </div>
      </header>
      {children}
      <footer className="mx-auto max-w-2xl px-6 py-8">
        <p className="text-[12px] text-ink-400">
          Powered by Relaydesk
        </p>
      </footer>
    </div>
  );
}

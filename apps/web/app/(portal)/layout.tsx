import { headers } from "next/headers";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { PortalFooter } from "@/components/portal/portal-footer";
import { PortalNav } from "@/components/portal/portal-nav";
import { getPublicWorkspace } from "@/lib/api/public";

/**
 * The customer-facing portal. It shares Relaydesk's tokens but none of the
 * console chrome -- served on the tenant's own subdomain.
 *
 * The workspace comes from `x-relaydesk-workspace`, a header the middleware
 * sets after resolving the request's Host against the portal domain (see
 * middleware.ts). No slug in the header, or a slug that does not resolve to
 * a workspace, both render Next's 404 -- the same response either way, so
 * neither leaks which workspaces exist.
 */
export default async function PortalLayout({ children }: { children: ReactNode }) {
  const slug = (await headers()).get("x-relaydesk-workspace");
  if (!slug) notFound();
  const workspace = await getPublicWorkspace(slug);
  if (!workspace) notFound();

  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-ink-200">
        <div className="mx-auto flex h-14 max-w-2xl items-center gap-2 px-6">
          <span className="flex size-6 items-center justify-center rounded-md bg-ink-900 text-[10px] font-semibold text-white">
            {workspace.monogram}
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-ink-900">
            {workspace.name}
          </span>
          <PortalNav />
        </div>
      </header>
      {children}
      <PortalFooter />
    </div>
  );
}

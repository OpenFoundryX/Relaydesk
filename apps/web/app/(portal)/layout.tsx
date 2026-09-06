import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { Suspense, type ReactNode } from "react";

import { PortalFooter } from "@/components/portal/portal-footer";
import { PortalNav } from "@/components/portal/portal-nav";
import { PortalSearch } from "@/components/portal/portal-search";
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
    <div className="flex min-h-screen flex-col bg-white">
      <header className="border-b border-ink-200">
        <div className="mx-auto flex min-h-14 max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-6 py-2.5">
          <span className="flex items-center gap-2">
            <span className="flex size-6 items-center justify-center rounded-md bg-ink-900 text-[10px] font-semibold text-white">
              {workspace.monogram}
            </span>
            <span className="text-[15px] font-semibold tracking-tight text-ink-900">
              {workspace.name}
            </span>
          </span>
          {/*
           * Search sits in the header rather than on the two pages that
           * used to carry a copy each, so it is reachable from an article
           * and from the ticket form as well as from the index. It reads
           * `?q=` to prefill itself, which is a dynamic read -- hence the
           * boundary, the way the console does it in
           * app/(console)/knowledge-base/layout.tsx.
           */}
          <Suspense fallback={<div className="h-9 min-w-0 flex-1 sm:max-w-xs" />}>
            <PortalSearch className="min-w-0 flex-1 sm:max-w-xs" />
          </Suspense>
          <PortalNav />
        </div>
      </header>
      <div className="flex-1">{children}</div>
      <PortalFooter />
    </div>
  );
}

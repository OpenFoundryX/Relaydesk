import { headers } from "next/headers";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { PortalFooter } from "@/components/portal/portal-footer";
import { PortalHero } from "@/components/portal/portal-hero";
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
      <PortalHero name={workspace.name} monogram={workspace.monogram} />
      <div className="flex-1">{children}</div>
      <PortalFooter />
    </div>
  );
}

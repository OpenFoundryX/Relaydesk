import "server-only";

import { cache } from "react";

import { getEmailChannels } from "./channels";

/**
 * The domain every workspace's public help site hangs off, as a
 * `host[:port]`. Mirrors `middleware.ts`, which resolves the other
 * direction -- a Host header back into a workspace slug.
 */
const PORTAL_DOMAIN = process.env.NEXT_PUBLIC_PORTAL_DOMAIN ?? "localhost:3000";

/**
 * Whether the portal is reached over http or https. Taken from the console's
 * own configured URL rather than assumed, so a local stack on
 * `http://localhost:3000` does not get sent to an https origin that is not
 * listening -- the same `WEB_URL ?? NEXT_PUBLIC_WEB_URL` pair
 * `lib/google-oauth.ts` reads.
 */
function portalProtocol(): string {
  const configured =
    process.env.WEB_URL ?? process.env.NEXT_PUBLIC_WEB_URL ?? "http://localhost:3000";
  try {
    return new URL(configured).protocol;
  } catch {
    return "http:";
  }
}

/**
 * Recovers the workspace's own slug from an ingest address.
 *
 * The API builds these as `{slug}-{ingestToken}@{inbound domain}` -- see
 * `address_for` in `services/channel_accounts.py`. Splitting on the *last*
 * dash is the API's own rule for pulling the two apart (`token_from_address`
 * in the same module): a workspace slug may contain dashes, the token never
 * does.
 */
function slugFromAddress(address: string): string | null {
  const local = address.split("@", 1)[0]?.trim().toLowerCase() ?? "";
  const cut = local.lastIndexOf("-");
  if (cut <= 0) return null;
  return local.slice(0, cut);
}

/**
 * The origin of this workspace's public help site, e.g.
 * `http://chronon.localhost:3000`, or `null` when it cannot be worked out.
 *
 * Every workspace is reached at `<slug>.<portal domain>` (see README), so
 * building that URL needs the slug -- and the slug is the one thing about a
 * workspace the console is never told directly: `GET /auth/me` returns id,
 * name, monogram, plan and counters, and the API is fixed. It does reach the
 * console in exactly one place, an email channel's ingest address, and every
 * workspace has at least one: `create_workspace` opens a default "Support"
 * channel account in the same transaction, because a workspace with no way
 * to receive mail is not a workspace.
 *
 * `null` is a real answer rather than a failure -- the caller disables
 * Preview instead of offering a link into a 404.
 */
export const getPortalOrigin = cache(async (): Promise<string | null> => {
  const channels = await getEmailChannels();
  for (const channel of channels) {
    const slug = slugFromAddress(channel.address);
    if (slug) return `${portalProtocol()}//${slug}.${PORTAL_DOMAIN}`;
  }
  return null;
});

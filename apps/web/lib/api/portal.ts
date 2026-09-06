import "server-only";

import { getWorkspace } from "./workspace";

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
 * The origin of this workspace's public help site, e.g.
 * `http://chronon.localhost:3000`.
 *
 * Every workspace is reached at `<slug>.<portal domain>` (see README), and
 * the slug comes straight from the workspace the session belongs to. It is
 * stable: renaming a workspace does not touch it, because it is the address
 * of every article the workspace has already published.
 */
export async function getPortalOrigin(): Promise<string> {
  const { slug } = await getWorkspace();
  return `${portalProtocol()}//${slug}.${PORTAL_DOMAIN}`;
}

"use server";

import { headers } from "next/headers";

import { ApiError } from "@/lib/api/client";
import { submitPublicTicket } from "@/lib/api/public";

export type SubmitTicketResult = { ok: true } | { ok: false; message: string };

function failure(error: unknown): { ok: false; message: string } {
  if (error instanceof ApiError) return { ok: false, message: error.message };
  throw error;
}

/**
 * The only path a portal ticket reaches the API through.
 *
 * The workspace comes solely from the `x-relaydesk-workspace` header the
 * middleware set after resolving the request's Host (see middleware.ts) --
 * never read from `formData` -- because a form field is something the
 * submitter controls. If the slug could travel that way, a submitter could
 * name any tenant's workspace and file a ticket straight into its inbox.
 *
 * The submitter's address travels the same indirect route. Next's own
 * server stamps `x-forwarded-for` from the raw socket address onto every
 * request that did not already arrive with one set (that is Next's
 * behaviour, not something this app configures), so what `headers()` sees
 * here is the address that connected to the Next server. Forwarding it as
 * `X-Forwarded-For` on the call to the API gives the API's rate limiter the
 * customer's address instead of the Next server's -- without this, every
 * portal submission would look like it came from the same place and share
 * one bucket. The API only believes the header from a peer listed in
 * `TRUSTED_PROXY_IPS` (see docker-compose.yml and the README); this side of
 * the wiring is the other half of that control.
 */
export async function submitTicketAction(formData: FormData): Promise<SubmitTicketResult> {
  const headerList = await headers();
  const slug = headerList.get("x-relaydesk-workspace");
  if (!slug) {
    // Unreachable in the normal flow -- the portal layout already 404s
    // before this form can render without a resolved workspace -- but a
    // server action gets no such gate for free, so it is checked here too
    // rather than trusting the render path was the only way in.
    return { ok: false, message: "This workspace could not be found." };
  }

  try {
    await submitPublicTicket(slug, formData, headerList.get("x-forwarded-for"));
    return { ok: true };
  } catch (error) {
    return failure(error);
  }
}

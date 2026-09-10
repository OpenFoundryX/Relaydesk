"use server";

import { headers } from "next/headers";

import { ApiError } from "@/lib/api/client";
import { submitWidgetTicket } from "@/lib/api/widget";

export type SubmitWidgetTicketResult = { ok: true } | { ok: false; message: string };

function failure(error: unknown): { ok: false; message: string } {
  if (error instanceof ApiError) return { ok: false, message: error.message };
  throw error;
}

/**
 * The only path a widget submission reaches the API through (spec D9,
 * mirroring `app/(portal)/submit-ticket/actions.ts` one door over).
 *
 * `key` travels as an explicit argument rather than a resolved header --
 * the widget has no subdomain to resolve one from (spec D3) -- but the
 * caller's address still travels indirectly: Next stamps `x-forwarded-for`
 * onto every request that did not already arrive with one (its own
 * behaviour, not something this app configures), and forwarding it here
 * gives the API's rate limiter the visitor's address rather than this
 * server's. The API only believes it from a peer in `TRUSTED_PROXY_IPS`
 * (see docker-compose.yml, the Caddyfile and middleware.ts).
 */
export async function submitWidgetTicketAction(
  key: string,
  formData: FormData,
): Promise<SubmitWidgetTicketResult> {
  const forwardedFor = (await headers()).get("x-forwarded-for");
  try {
    await submitWidgetTicket(key, formData, forwardedFor);
    return { ok: true };
  } catch (error) {
    return failure(error);
  }
}

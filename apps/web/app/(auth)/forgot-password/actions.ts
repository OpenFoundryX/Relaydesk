"use server";

import { headers } from "next/headers";

import { ApiError } from "@/lib/api/client";
import { requestPasswordReset } from "@/lib/api/password-reset";

export type RequestPasswordResetResult =
  | { ok: true }
  | { ok: false; message: string };

/**
 * Reports nothing account-dependent. The API answers 202 for every address;
 * surfacing anything that varies with *which account* was typed -- an
 * error, a "no such account", even a different spinner duration -- would
 * reintroduce the enumeration oracle the API is careful not to be.
 *
 * That does not extend to input-syntax or transport failures, which are not
 * an oracle at all: a `422` (the address fails `EmailStr`, e.g. "me@company"
 * with no TLD) and a network error happen identically regardless of whether
 * an account exists behind the address, so surfacing them leaks nothing.
 * Left uncaught, an `ApiError` here escaped the transition and hit Next's
 * generic application-error screen instead of this page -- worse for the
 * user than a neutral message, for no privacy benefit. A `422` gets its own
 * neutral copy; anything else falls through to the same "Check your email"
 * panel `sent: true` already shows, so a transient API failure reads no
 * differently than success. Same shape as `login/actions.ts`'s `signIn` and
 * `invites/actions.ts`.
 */
export async function requestPasswordResetAction(
  email: string,
): Promise<RequestPasswordResetResult> {
  const headerList = await headers();
  const forwardedFor = headerList.get("x-forwarded-for");

  try {
    await requestPasswordReset(email, forwardedFor);
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 422) {
        return { ok: false, message: "That email address doesn't look right." };
      }
      // Any other failure (rate limit, network blip, 5xx) is treated as if
      // it succeeded from the caller's point of view -- see the docstring.
      return { ok: true };
    }
    throw error;
  }
}

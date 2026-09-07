"use server";

import { requestPasswordReset } from "@/lib/api/password-reset";

/**
 * Returns nothing and reports nothing. The API answers 202 for every
 * address; surfacing anything else here — an error, a "no such account",
 * even a different spinner duration — would reintroduce the enumeration
 * oracle the API is careful not to be.
 */
export async function requestPasswordResetAction(email: string): Promise<void> {
  await requestPasswordReset(email);
}

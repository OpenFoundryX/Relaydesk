"use server";

import { ApiError } from "@/lib/api/client";
import { confirmPasswordReset } from "@/lib/api/password-reset";

export type ConfirmResult =
  | { ok: true }
  | { ok: false; invalid: true }
  | { ok: false; invalid: false; message: string };

/**
 * The token lives only in the URL fragment (see page.tsx), so the client
 * component passes it as a plain argument — never a query string — keeping
 * it out of this request's own URL too.
 */
export async function confirmPasswordResetAction(
  token: string,
  password: string,
): Promise<ConfirmResult> {
  try {
    await confirmPasswordReset(token, password);
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 404) return { ok: false, invalid: true };
      return { ok: false, invalid: false, message: error.message };
    }
    throw error;
  }
}

"use server";

import { redirect } from "next/navigation";

import { ApiError } from "@/lib/api/client";
import { acceptInvite } from "@/lib/api/invites";
import { setSessionCookie } from "@/lib/session";

/**
 * Accepting signs you in: the API returns a session token, exactly as
 * /auth/login does, so the new member lands in the inbox rather than on a
 * second sign-in form.
 */
export async function accept(formData: FormData) {
  const token = String(formData.get("token") ?? "");
  const name = String(formData.get("name") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  const back = `/invite/${encodeURIComponent(token)}`;
  if (!name || !password) redirect(`${back}?error=fields`);

  let session: { token: string; expiresAt: string };
  try {
    session = await acceptInvite(token, name, password);
  } catch (error) {
    // `redirect` throws, so it has to sit outside the try — and an
    // ApiError's own message is the API's, which is safe to re-render only
    // as one of the codes the page knows how to phrase.
    if (error instanceof ApiError) redirect(`${back}?error=${error.status}`);
    throw error;
  }

  await setSessionCookie(session.token, session.expiresAt);
  redirect("/conversations?status=open");
}

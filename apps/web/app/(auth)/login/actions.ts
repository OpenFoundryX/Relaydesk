"use server";

import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api/client";
import { clearSessionCookie, setSessionCookie } from "@/lib/session";

interface TokenResponse {
  token: string;
  expiresAt: string;
}

export async function signIn(formData: FormData) {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  let token: TokenResponse;
  try {
    token = await apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      auth: false,
      body: JSON.stringify({ email, password }),
    });
  } catch (error) {
    if (error instanceof ApiError) redirect("/login?error=1");
    throw error;
  }

  await setSessionCookie(token.token, token.expiresAt);
  redirect("/conversations?status=open");
}

export async function signOut() {
  await apiFetch<void>("/auth/logout", { method: "POST" }).catch(() => undefined);
  await clearSessionCookie();
  redirect("/login");
}

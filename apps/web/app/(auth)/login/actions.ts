"use server";

import { cookies } from "next/headers";
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

export async function signInWithGoogle() {
  const redirectUri = `${process.env.NEXT_PUBLIC_WEB_URL ?? "http://localhost:3000"}/login/google/callback`;

  let url: string;
  let state: string;
  try {
    ({ url, state } = await apiFetch<{ url: string; state: string }>(
      `/auth/google/url?redirectUri=${encodeURIComponent(redirectUri)}`,
      { auth: false },
    ));
  } catch (error) {
    if (error instanceof ApiError) redirect("/login?error=1");
    throw error;
  }

  const store = await cookies();
  store.set("rd_oauth_state", state, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 600,
  });

  redirect(url);
}

export async function signOut() {
  await apiFetch<void>("/auth/logout", { method: "POST" }).catch(() => undefined);
  await clearSessionCookie();
  redirect("/login");
}

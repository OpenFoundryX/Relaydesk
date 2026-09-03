import "server-only";

import { redirect } from "next/navigation";

import { getSessionToken } from "@/lib/session";

const apiUrl = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Options = RequestInit & { auth?: boolean };

/**
 * Server-side fetch against the Relaydesk API.
 *
 * Attaches the session token as a bearer header. A 401 on an authenticated
 * call means the session died underneath us, so we send the user to
 * /signed-out (a route handler that clears the stale cookie before bouncing
 * to /login) rather than surfacing a raw error inside a console screen. We
 * cannot clear the cookie here: this runs during Server Component render,
 * where Next forbids mutating cookies.
 */
export async function apiFetch<T>(path: string, options: Options = {}): Promise<T> {
  const { auth = true, headers, ...init } = options;
  const token = auth ? await getSessionToken() : null;

  const response = await fetch(`${apiUrl}/api${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  if (response.status === 204) return undefined as T;

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const code = body?.error?.code ?? "error";
    const message = body?.error?.message ?? `Request failed with ${response.status}`;
    if (response.status === 401 && auth) redirect("/signed-out");
    throw new ApiError(response.status, code, message);
  }

  return (await response.json()) as T;
}

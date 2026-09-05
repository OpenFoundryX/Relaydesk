import "server-only";

import { redirect } from "next/navigation";

import { getSessionToken } from "@/lib/session";

export const apiUrl =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
 * Trace every API call in the server console.
 *
 * These calls are made by the Next server, not the browser, so they never
 * appear in a browser Network tab — that is the point of the seam, since it
 * keeps the session token out of client JS. This is the equivalent view:
 *
 *   [api] GET /conversations?status=open -> 200 in 12ms
 *
 * Visible with `docker compose logs -f web`. Silent in production.
 */
function trace(method: string, path: string, outcome: string, startedAt: number): void {
  if (process.env.NODE_ENV === "production") return;
  const ms = Math.round(performance.now() - startedAt);
  console.info(`[api] ${method} ${path} -> ${outcome} in ${ms}ms`);
}

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
  const method = init.method ?? "GET";
  const startedAt = performance.now();

  let response: Response;
  try {
    response = await fetch(`${apiUrl}/api${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
    });
  } catch (error) {
    // The API being unreachable is the one failure with no status to report.
    trace(method, path, "NETWORK ERROR", startedAt);
    throw error;
  }

  trace(method, path, String(response.status), startedAt);

  if (response.status === 204) return undefined as T;

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const code = body?.error?.code ?? "error";
    const message = body?.error?.message ?? `Request failed with ${response.status}`;
    if (response.status === 401 && auth) redirect("/signed-out");
    throw new ApiError(response.status, code, message);
  }

  // A 202 (e.g. `POST /team/invites`, which sends the invite by email rather
  // than handing anything back) has no body either, but no distinct status
  // code to special-case on the way in -- so parse only when there is
  // something to parse.
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

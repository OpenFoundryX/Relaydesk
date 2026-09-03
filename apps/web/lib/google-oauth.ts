import "server-only";

/**
 * The redirect_uri sent to Google must be byte-identical between the
 * authorization request (`signInWithGoogle`) and the token exchange (the
 * callback route), or Google rejects the exchange outright. Centralizing
 * it here means the two call sites cannot drift apart from each other.
 *
 * Prefers the server-only `WEB_URL` (the same name the API already uses in
 * config.py) over `NEXT_PUBLIC_WEB_URL`: NEXT_PUBLIC_* variables are
 * inlined into the client bundle at `next build` time, so a production
 * image built without one set would silently bake in the build-time
 * fallback. `WEB_URL` is read at request time instead. Falling back to
 * NEXT_PUBLIC_WEB_URL keeps this working for setups that only set that one,
 * then to localhost for a fresh clone with neither set.
 */
export function googleRedirectUri(): string {
  const base =
    process.env.WEB_URL ?? process.env.NEXT_PUBLIC_WEB_URL ?? "http://localhost:3000";
  return `${base}/login/google/callback`;
}

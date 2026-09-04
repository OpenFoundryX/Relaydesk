import AuthLayout from "@/app/(auth)/layout";

/**
 * Accepting an invite is an auth screen: same logo-over-centred-card chrome
 * as /login. Reused rather than copied so the two cannot drift apart.
 *
 * It lives outside the (auth) route group because the route must stay
 * reachable unauthenticated at exactly /invite/<token> — the URL the API
 * mints in `inviteUrl`.
 */
export default AuthLayout;

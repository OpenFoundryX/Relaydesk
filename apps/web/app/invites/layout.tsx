import type { Metadata } from "next";

import AuthLayout from "@/app/(auth)/layout";

export const metadata: Metadata = { title: "Accept invite" };

/**
 * Accepting an invite is an auth screen: same logo-over-centred-card chrome
 * as /login. Reused rather than copied so the two cannot drift apart.
 *
 * It lives outside the (auth) route group because the route must stay
 * reachable unauthenticated at exactly /invites -- the URL the invite email
 * links to, with the token appended as a fragment the server never sees.
 */
export default AuthLayout;

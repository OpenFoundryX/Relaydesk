"use server";

import { redirect } from "next/navigation";

/**
 * Placeholder sign-in. There is no auth backend yet, so any submission lands
 * in the console; swap the body for a real session exchange when it exists.
 */
export async function signIn() {
  redirect("/conversations?status=open");
}

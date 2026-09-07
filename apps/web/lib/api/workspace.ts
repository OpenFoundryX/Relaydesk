import "server-only";

import { notFound } from "next/navigation";
import { cache } from "react";

import { apiFetch } from "@/lib/api/client";
import type { CurrentUser, Workspace } from "@/lib/types";

interface MeResponse {
  user: CurrentUser;
  workspace: Workspace;
  membership: { role: "admin" | "agent" };
}

export const getMe = cache(async (): Promise<MeResponse> => {
  return apiFetch<MeResponse>("/auth/me");
});

export async function getWorkspace(): Promise<Workspace> {
  return (await getMe()).workspace;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return (await getMe()).user;
}

export async function isAdmin(): Promise<boolean> {
  return (await getMe()).membership.role === "admin";
}

/**
 * Guard for a console page that exists only to configure the workspace.
 *
 * `notFound()` rather than a redirect, so an agent who guesses the URL is not
 * told the page exists. This is the console half of the check only — the API
 * enforces the same rule independently in `WorkspaceScope.require_admin`, and
 * remains the authority. A page whose data the API already serves to agents
 * (channels, team) is not guarded here; it gates its actions instead.
 */
export async function requireAdmin(): Promise<void> {
  if (!(await isAdmin())) {
    notFound();
  }
}

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

/**
 * Change the workspace's own details. Admin-only in the API, which is where
 * that is enforced -- a 403 comes back as an `ApiError` for the caller to
 * show.
 *
 * The slug is deliberately not among the fields: it is the workspace's
 * subdomain, so every published help-centre link is built from it.
 */
export async function updateWorkspace(patch: {
  name?: string;
  monogram?: string;
  timezone?: string;
}): Promise<Workspace> {
  return apiFetch<Workspace>("/workspace", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
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

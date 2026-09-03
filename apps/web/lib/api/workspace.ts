import "server-only";

import { apiFetch } from "@/lib/api/client";
import type { CurrentUser, Workspace } from "@/lib/types";

interface MeResponse {
  user: CurrentUser;
  workspace: Workspace;
  membership: { role: "admin" | "agent" };
}

export async function getMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/auth/me");
}

export async function getWorkspace(): Promise<Workspace> {
  return (await getMe()).workspace;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return (await getMe()).user;
}

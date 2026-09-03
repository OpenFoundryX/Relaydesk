import "server-only";

import { apiFetch } from "@/lib/api/client";
import type { SetupTask, TeamMember } from "@/lib/types";

export async function getTeam(): Promise<TeamMember[]> {
  return apiFetch<TeamMember[]>("/team");
}

export async function getSetupTasks(): Promise<SetupTask[]> {
  return apiFetch<SetupTask[]>("/workspace/setup-tasks");
}

import "server-only";

import { cache } from "react";

import { apiFetch } from "./client";
import type { ApiKey, ApiKeyCreated, ApiKeyScope } from "@/lib/types";

export const getApiKeys = cache(async (): Promise<ApiKey[]> => {
  return apiFetch<ApiKey[]>("/api-keys");
});

export async function createApiKey(
  name: string,
  scopes: ApiKeyScope[],
): Promise<ApiKeyCreated> {
  return apiFetch<ApiKeyCreated>("/api-keys", {
    method: "POST",
    body: JSON.stringify({ name, scopes }),
  });
}

export async function revokeApiKey(id: string): Promise<void> {
  await apiFetch(`/api-keys/${id}`, { method: "DELETE" });
}

import "server-only";

import { cache } from "react";

import { apiFetch } from "./client";

/**
 * A workspace's model configuration (spec Task 1/9). One row per workspace,
 * admin-only, reached at `/ai-config`.
 *
 * There is deliberately no `apiKey` field: the key is write-only end to end
 * -- set through `updateAiConfig`, never read back. `keySuffix` is the
 * masked tail the console shows instead, so an admin can tell which key is
 * installed without ever being handed it. Every schema on the API side
 * inherits `CamelModel`, so the wire is already camelCase.
 */
export interface AiConfig {
  provider: string;
  model: string;
  baseUrl: string | null;
  dailyTokenBudget: number;
  enabled: boolean;
  keySuffix: string | null;
}

/**
 * A field left out is how the console leaves it alone -- `apiKey` omitted
 * keeps the installed key, `apiKey: ""` clears it. See `AiConfigIn` on the
 * API side.
 */
export interface AiConfigInput {
  provider?: string;
  model?: string;
  apiKey?: string;
  baseUrl?: string;
  dailyTokenBudget?: number;
  enabled?: boolean;
}

export const getAiConfig = cache(async (): Promise<AiConfig> => {
  return apiFetch<AiConfig>("/ai-config");
});

export async function updateAiConfig(patch: AiConfigInput): Promise<AiConfig> {
  return apiFetch<AiConfig>("/ai-config", {
    method: "PUT",
    body: JSON.stringify(patch),
  });
}

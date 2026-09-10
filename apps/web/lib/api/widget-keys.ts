import "server-only";

import { cache } from "react";

import { apiFetch } from "./client";

/**
 * A console-managed widget embed (spec D1/D4). Admin-only, reached under
 * `/widget-keys` -- not to be confused with `lib/api/widget.ts`, the
 * anonymous door the embedded widget itself calls by key.
 *
 * Every schema on the API side inherits `CamelModel`, so the wire is already
 * camelCase and needs no mapping layer here.
 */
export interface WidgetKey {
  id: string;
  name: string;
  /**
   * Returned in full on every read, unlike `ApiKey`'s one-time token. This
   * value is public by construction -- it is meant to sit in the customer's
   * page source, so there is nothing to protect by hiding it after creation.
   */
  key: string;
  allowedOrigins: string[];
  /** Launcher colour, position, greeting and the like. Deliberately not
   * rendered anywhere in this slice -- see the widget settings page brief. */
  settings: Record<string, unknown>;
  active: boolean;
  lastSeenAt: string | null;
  createdAt: string;
}

export interface WidgetKeyInput {
  name: string;
  allowedOrigins?: string[];
}

export const getWidgetKeys = cache(async (): Promise<WidgetKey[]> => {
  return apiFetch<WidgetKey[]>("/widget-keys");
});

export async function createWidgetKey(input: WidgetKeyInput): Promise<WidgetKey> {
  return apiFetch<WidgetKey>("/widget-keys", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateWidgetKey(
  id: string,
  patch: Partial<WidgetKeyInput> & { active?: boolean },
): Promise<WidgetKey> {
  return apiFetch<WidgetKey>(`/widget-keys/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function deleteWidgetKey(id: string): Promise<void> {
  await apiFetch(`/widget-keys/${id}`, { method: "DELETE" });
}

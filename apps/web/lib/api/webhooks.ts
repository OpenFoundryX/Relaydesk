import "server-only";

import { cache } from "react";

import { apiFetch } from "./client";
import type { Webhook, WebhookCreated, WebhookParam, WebhookTestResult } from "@/lib/types";

export interface WebhookInput {
  name: string;
  description: string;
  method: Webhook["method"];
  url: string;
  params: WebhookParam[];
}

export const getWebhooks = cache(async (): Promise<Webhook[]> => {
  return apiFetch<Webhook[]>("/webhooks");
});

/** The response carries the signing secret. Unlike an API key's token it is
 * recoverable — by rotating it — but it is not in the list response, so this
 * is the only place it appears without an admin asking for a new one. */
export async function createWebhook(input: WebhookInput): Promise<WebhookCreated> {
  return apiFetch<WebhookCreated>("/webhooks", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateWebhook(
  id: string,
  patch: Partial<WebhookInput>,
): Promise<Webhook> {
  return apiFetch<Webhook>(`/webhooks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function deleteWebhook(id: string): Promise<void> {
  await apiFetch(`/webhooks/${id}`, { method: "DELETE" });
}

export async function rotateWebhookSecret(id: string): Promise<WebhookCreated> {
  return apiFetch<WebhookCreated>(`/webhooks/${id}/secret`, { method: "POST" });
}

/**
 * Fire one signed request at the endpoint and report what came back.
 *
 * A receiver that answers 500 is a *successful* test that found a broken
 * endpoint, so this resolves rather than throws; only a bad argument (which
 * means no request was made at all) comes back as an `ApiError`.
 */
export async function testWebhook(
  id: string,
  argumentValues: Record<string, string>,
): Promise<WebhookTestResult> {
  return apiFetch<WebhookTestResult>(`/webhooks/${id}/test`, {
    method: "POST",
    body: JSON.stringify({ arguments: argumentValues }),
  });
}

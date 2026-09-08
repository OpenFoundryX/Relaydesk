"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api/client";
import {
  createWebhook,
  deleteWebhook,
  rotateWebhookSecret,
  testWebhook,
  type WebhookInput,
} from "@/lib/api/webhooks";
import type { WebhookTestResult } from "@/lib/types";

export type SecretResult = { ok: true; secret: string } | { ok: false; message: string };
export type DeleteResult = { ok: true } | { ok: false; message: string };
export type TestResult =
  | { ok: true; result: WebhookTestResult }
  | { ok: false; message: string };

function refresh() {
  revalidatePath("/", "layout");
}

export async function createWebhookAction(input: WebhookInput): Promise<SecretResult> {
  try {
    const created = await createWebhook(input);
    refresh();
    return { ok: true, secret: created.secret };
  } catch (error) {
    // A non-admin gets a 403, a bad name or URL a 422, a duplicate name a 409.
    // The page already hides these controls from agents; this is what stands
    // between a stale client and an error boundary. Compare
    // settings/api-keys/actions.ts.
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}

export async function rotateWebhookSecretAction(id: string): Promise<SecretResult> {
  try {
    const rotated = await rotateWebhookSecret(id);
    refresh();
    return { ok: true, secret: rotated.secret };
  } catch (error) {
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}

export async function deleteWebhookAction(id: string): Promise<DeleteResult> {
  try {
    await deleteWebhook(id);
    refresh();
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}

/**
 * No `refresh()` here: a test request changes nothing that any page renders.
 * It is a question put to the customer's endpoint, and the answer belongs to
 * the component that asked.
 */
export async function testWebhookAction(
  id: string,
  argumentValues: Record<string, string>,
): Promise<TestResult> {
  try {
    return { ok: true, result: await testWebhook(id, argumentValues) };
  } catch (error) {
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}

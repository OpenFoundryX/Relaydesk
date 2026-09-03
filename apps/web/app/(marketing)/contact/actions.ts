"use server";

import { redirect } from "next/navigation";

/**
 * Placeholder contact handler. Nothing is stored yet; wire this to the API or
 * a CRM webhook when one exists. The redirect keeps the form free of client JS.
 */
export async function sendContact(formData: FormData) {
  const name = String(formData.get("name") ?? "").trim();
  redirect(`/contact?sent=1&name=${encodeURIComponent(name.split(" ")[0] ?? "")}`);
}

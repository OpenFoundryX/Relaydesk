import { redirect } from "next/navigation";

import { isAdmin } from "@/lib/api/workspace";

export default async function SettingsIndex() {
  // An agent has no workspace configuration to land on, only their own
  // profile, so the section's entry point differs by role. Sending everyone
  // to /settings/channels would drop an agent straight onto a 404.
  redirect((await isAdmin()) ? "/settings/channels" : "/settings/account");
}

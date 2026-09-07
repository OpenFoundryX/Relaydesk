import { redirect } from "next/navigation";

import { requireAdmin } from "@/lib/api/workspace";

export default async function UserPortalIndex() {
  await requireAdmin();

  redirect("/user-portal/general");
}

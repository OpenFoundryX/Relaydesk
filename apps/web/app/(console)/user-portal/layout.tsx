import type { ReactNode } from "react";

import { PageShell } from "@/components/console/page-shell";
import { requireAdmin } from "@/lib/api/workspace";

export default async function UserPortalLayout({
  children,
}: {
  children: ReactNode;
}) {
  // Unlike /settings, every page in this section is workspace configuration,
  // so the guard belongs on the layout rather than repeated on each page.
  await requireAdmin();

  return <PageShell className="max-w-4xl">{children}</PageShell>;
}

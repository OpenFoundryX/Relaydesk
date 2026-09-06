import type { ReactNode } from "react";

import { PageShell } from "@/components/console/page-shell";

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return <PageShell className="max-w-4xl">{children}</PageShell>;
}

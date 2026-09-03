import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@/components/console/logo";

/**
 * Auth screens: logo pinned to the top, content centred in the remaining
 * space, no site chrome.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="flex h-16 items-center justify-center">
        <Link href="/" aria-label="Relaydesk home">
          <Logo />
        </Link>
      </header>
      <main className="flex flex-1 items-center justify-center px-6 py-10">{children}</main>
      <p className="pb-6 text-center text-[12px] text-ink-400">
        © {new Date().getFullYear()} Relaydesk
      </p>
    </div>
  );
}

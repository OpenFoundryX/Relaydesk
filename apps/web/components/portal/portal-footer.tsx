"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * The help centre's deflection footer: a way to reach the ticket form when
 * the answer isn't in an article. Scoped to the /help surface only -- a
 * visitor already on the ticket form doesn't need to be told how to get to
 * it.
 *
 * The rule is on the outer element so it spans the viewport like the
 * header's does, while the text inside stays on the same grid as the page
 * above it.
 */
export function PortalFooter() {
  const pathname = usePathname();
  const onHelpCentre = pathname === "/help" || pathname.startsWith("/help/");

  return (
    <footer className="border-t border-ink-200">
      <div className="mx-auto max-w-5xl px-6 py-8">
        {onHelpCentre && (
          <p className="mb-3 text-[13px] text-ink-500">
            Can&apos;t find what you need?{" "}
            <Link
              href="/submit-ticket"
              className="font-medium text-accent-950 hover:underline"
            >
              Contact us
            </Link>
          </p>
        )}
        <p className="text-[12px] text-ink-400">Powered by Relaydesk</p>
      </div>
    </footer>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

/**
 * The two customer-facing portal surfaces. Both live on the same
 * subdomain -- see middleware.ts -- but nothing linked between them before
 * this nav existed, so a customer stuck on one had no path to the other.
 */
const LINKS = [
  { href: "/help", label: "Help center" },
  { href: "/submit-ticket", label: "Contact us" },
] as const;

/**
 * Portal-wide navigation, rendered in `(portal)/layout.tsx`'s shared
 * header. A client component (rather than server-rendered from the
 * layout) purely to read the current path for the active-link state --
 * the layout itself has no other reason to know it.
 */
export function PortalNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Portal" className="ml-auto flex items-center gap-4 text-[13px]">
      {LINKS.map(({ href, label }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "transition-colors",
              active ? "font-semibold text-ink-900" : "text-ink-500 hover:text-ink-900",
            )}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

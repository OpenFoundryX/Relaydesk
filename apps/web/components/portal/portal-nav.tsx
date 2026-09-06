"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, Ticket } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * The two customer-facing portal surfaces. Both live on the same
 * subdomain -- see middleware.ts -- but nothing linked between them before
 * this nav existed, so a customer stuck on one had no path to the other.
 *
 * Each carries an icon, the way every other navigation in this codebase
 * does (components/console/sidebar). The labels name what is behind them
 * rather than what the section is called internally: "Submit a ticket" is
 * the thing the second one does, where "Contact us" left a customer
 * guessing whether it meant a phone number.
 */
const LINKS = [
  { href: "/help", label: "Knowledge Base", icon: BookOpen },
  { href: "/submit-ticket", label: "Submit a ticket", icon: Ticket },
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
    <nav aria-label="Portal" className="flex items-center gap-4 text-[13px]">
      {LINKS.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-1.5 whitespace-nowrap transition-colors",
              active ? "font-semibold text-ink-900" : "text-ink-500 hover:text-ink-900",
            )}
          >
            <Icon aria-hidden className="size-4 shrink-0" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

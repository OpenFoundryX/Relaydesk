import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { Logo } from "@/components/console/logo";
import { PlatformMenu, ResourcesMenu } from "@/components/marketing/nav-menus";
import { Button } from "@/components/ui/button";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-ink-200/80 bg-white/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center px-6">
        <Link href="/" aria-label="Relaydesk home">
          <Logo />
        </Link>
        <nav className="ml-auto hidden items-center gap-1 md:flex" aria-label="Primary">
          <PlatformMenu />
          <ResourcesMenu />
          <Link
            href="/#pricing"
            className="inline-flex h-8 items-center rounded-md px-2 text-[13px] font-medium text-ink-600 transition-colors hover:text-ink-900"
          >
            Pricing
          </Link>
          <Link
            href="/contact"
            className="inline-flex h-8 items-center rounded-md px-2 text-[13px] font-medium text-ink-600 transition-colors hover:text-ink-900"
          >
            Book a demo
          </Link>
        </nav>
        <div className="ml-auto flex items-center gap-2 md:ml-4">
          <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild variant="primary" size="md">
            <Link href="/contact">
              Try for free
              <ChevronRight />
            </Link>
          </Button>
        </div>
      </div>
    </header>
  );
}

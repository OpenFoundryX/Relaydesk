import Link from "next/link";

import { PlatformMenu, ResourcesMenu } from "@/components/marketing/nav-menus";
import { PillLink } from "@/components/marketing/pill";
import { SiteLogo } from "@/components/marketing/site-logo";

/**
 * A single transparent bar: no background, no border, no shadow. Logo left,
 * links centre, a text link and one filled pill right.
 */
export function SiteHeader() {
  return (
    <header className="absolute inset-x-0 top-0 z-20">
      <div className="mx-auto flex h-20 max-w-[1200px] items-center px-6 lg:px-10">
        <Link href="/" aria-label="Relaydesk home">
          <SiteLogo />
        </Link>

        <nav
          className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-1 lg:flex"
          aria-label="Primary"
        >
          <PlatformMenu />
          <ResourcesMenu />
          <Link
            href="/#pricing"
            className="px-3 py-0.5 text-[16px] font-normal text-ink-black"
          >
            Pricing
          </Link>
          <Link
            href="https://github.com/openfoundry/relaydesk"
            className="px-3 py-0.5 text-[16px] font-normal text-ink-black"
          >
            Open source
          </Link>
        </nav>

        <div className="ml-auto flex items-center gap-5">
          <Link
            href="/login"
            className="hidden text-[16px] font-normal text-ink-black sm:inline"
          >
            Sign in
          </Link>
          <PillLink href="/contact" variant="filled" className="h-10">
            Get started
          </PillLink>
        </div>
      </div>
    </header>
  );
}

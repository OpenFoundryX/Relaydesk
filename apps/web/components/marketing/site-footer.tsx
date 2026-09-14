import Link from "next/link";

import { SiteLogo } from "@/components/marketing/site-logo";

const columns = [
  {
    title: "Product",
    links: [
      { label: "Grounded answers", href: "/#answers" },
      { label: "One inbox", href: "/#inbox" },
      { label: "Triage", href: "/#triage" },
      { label: "Agent tools", href: "/#agent" },
      { label: "Help centre", href: "/#portal" },
      { label: "Pricing", href: "/#pricing" },
    ],
  },
  {
    title: "Open source",
    links: [
      { label: "GitHub", href: "https://github.com/openfoundry/relaydesk" },
      {
        label: "Self-hosting guide",
        href: "https://github.com/openfoundry/relaydesk#start",
      },
      {
        label: "Contributing",
        href: "https://github.com/openfoundry/relaydesk/blob/main/CONTRIBUTING.md",
      },
      {
        label: "Security",
        href: "https://github.com/openfoundry/relaydesk/blob/main/SECURITY.md",
      },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "Contact us", href: "/contact" },
      { label: "Sign in", href: "/login" },
      {
        label: "Governance",
        href: "https://github.com/openfoundry/relaydesk/blob/main/GOVERNANCE.md",
      },
      {
        label: "License (AGPL-3.0)",
        href: "https://github.com/openfoundry/relaydesk/blob/main/LICENSE",
      },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-hairline bg-paper-white">
      <div className="mx-auto grid max-w-[1200px] gap-12 px-6 py-20 lg:px-10 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div>
          <SiteLogo />
          <p className="mt-5 max-w-xs text-caption text-slate-gray">
            Answers the repeat questions out of your own help articles. Tells you
            when it cannot. Self-host it, or let us run it.
          </p>
        </div>
        {columns.map((column) => (
          <div key={column.title}>
            <h3 className="text-[14px] font-normal text-ash-gray">
              {column.title}
            </h3>
            <ul className="mt-5 space-y-3">
              {column.links.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-[15px] text-slate-gray transition-colors hover:text-ink-black"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-hairline">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-2 px-6 py-6 lg:px-10 text-[14px] text-smoke-gray sm:flex-row sm:items-center sm:justify-between">
          <span>
            © {new Date().getFullYear()} Relaydesk. Released under the AGPL-3.0
            license.
          </span>
          <span>Built in the open.</span>
        </div>
      </div>
    </footer>
  );
}

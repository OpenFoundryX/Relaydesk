import Link from "next/link";

import { Logo } from "@/components/console/logo";

const columns = [
  {
    title: "Product",
    links: [
      { label: "Unified inbox", href: "/#product" },
      { label: "AI triage", href: "/#triage" },
      { label: "AI agent", href: "/#agent" },
      { label: "User portal", href: "/#portal" },
      { label: "Pricing", href: "/#pricing" },
      { label: "Sign in", href: "/login" },
    ],
  },
  {
    title: "Open source",
    links: [
      { label: "GitHub", href: "https://github.com/openfoundry/relaydesk" },
      { label: "Self-hosting guide", href: "https://github.com/openfoundry/relaydesk#start" },
      { label: "Contributing", href: "https://github.com/openfoundry/relaydesk/blob/main/CONTRIBUTING.md" },
      { label: "Security", href: "https://github.com/openfoundry/relaydesk/blob/main/SECURITY.md" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "Contact us", href: "/contact" },
      { label: "Governance", href: "https://github.com/openfoundry/relaydesk/blob/main/GOVERNANCE.md" },
      { label: "Support", href: "https://github.com/openfoundry/relaydesk/blob/main/SUPPORT.md" },
      { label: "License (AGPL-3.0)", href: "https://github.com/openfoundry/relaydesk/blob/main/LICENSE" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-ink-200 bg-white">
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-14 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div>
          <Logo />
          <p className="mt-3 max-w-xs text-[13px] leading-relaxed text-ink-500">
            Open-source AI-native customer support. Self-host it, or let us run it
            for you.
          </p>
        </div>
        {columns.map((column) => (
          <div key={column.title}>
            <h3 className="text-[12px] font-semibold uppercase tracking-wide text-ink-500">
              {column.title}
            </h3>
            <ul className="mt-3 space-y-2">
              {column.links.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-[13px] text-ink-700 transition-colors hover:text-ink-900"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-ink-200">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 py-5 text-[12px] text-ink-400 sm:flex-row sm:items-center sm:justify-between">
          <span>© {new Date().getFullYear()} Relaydesk. Released under the AGPL-3.0 license.</span>
          <span>Built in the open.</span>
        </div>
      </div>
    </footer>
  );
}

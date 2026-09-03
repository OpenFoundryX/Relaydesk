/**
 * Competitor comparison pages. We only make claims about Relaydesk here; the
 * competitor is named for context and the reasons are phrased as what teams
 * moving off that tool tell us they wanted.
 */
export interface Competitor {
  slug: string;
  name: string;
  /** Short framing of the kind of team that usually runs it. */
  audience: string;
  reasons: string[];
}

export const competitors: Competitor[] = [
  {
    slug: "zendesk",
    name: "Zendesk",
    audience: "large support orgs with dedicated admins",
    reasons: [
      "Fewer moving parts: one inbox, one settings page, no marketplace to assemble",
      "AI that can act on tickets, not only suggest macros",
      "Pricing by ticket volume rather than by agent seat",
    ],
  },
  {
    slug: "freshdesk",
    name: "Freshdesk",
    audience: "teams that want a quick start and grow into add-ons",
    reasons: [
      "Triage rules written in plain language instead of nested conditions",
      "The full codebase is open, so nothing is gated behind a tier",
      "Self-hosting when data residency matters",
    ],
  },
  {
    slug: "help-scout",
    name: "Help Scout",
    audience: "small teams that value a clean shared inbox",
    reasons: [
      "The same simple inbox, plus an agent that resolves routine tickets",
      "Discord and an API alongside email",
      "Connect Stripe and your database so replies carry account context",
    ],
  },
  {
    slug: "zoho-desk",
    name: "Zoho Desk",
    audience: "companies already inside the Zoho suite",
    reasons: [
      "Integrates with the tools you use rather than a single vendor suite",
      "Custom webhooks and MCP servers for your own actions",
      "A public roadmap and an AGPL license",
    ],
  },
  {
    slug: "intercom",
    name: "Intercom",
    audience: "product-led companies that lean on in-app messaging",
    reasons: [
      "Built for tickets first: statuses, priorities, assignment, SLAs",
      "Predictable, volume-based pricing with no per-resolution fees",
      "Run it yourself with Docker Compose and your own model keys",
    ],
  },
];

export function getCompetitor(slug: string) {
  return competitors.find((competitor) => competitor.slug === slug);
}

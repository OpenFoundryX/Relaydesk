import type { KbCategory } from "./types";

/**
 * Internal articles are procedures the AI agent follows; external articles are
 * the customer-facing user guide. External ships empty so the app exercises
 * both the populated and the empty layout.
 */
const internal: KbCategory[] = [
  {
    id: "billing",
    name: "Billing",
    articles: [
      {
        id: "refund-request",
        title: "Handling a refund request",
        excerpt:
          "Verify the charge in Stripe, confirm it falls inside the 30-day window, then issue through the refund webhook.",
        status: "published",
        updatedAt: "2026-08-24",
      },
      {
        id: "duplicate-charge",
        title: "Duplicate charge on one invoice",
        excerpt:
          "Match both invoice IDs, void the later one, and reply with the credit note attached.",
        status: "published",
        updatedAt: "2026-08-19",
      },
      {
        id: "plan-downgrade",
        title: "Downgrading a workspace mid-cycle",
        excerpt:
          "Downgrades take effect at renewal. Never prorate without an admin approving it first.",
        status: "ready",
        updatedAt: "2026-08-27",
      },
    ],
  },
  {
    id: "returns",
    name: "Returns",
    articles: [
      {
        id: "rma",
        title: "Opening an RMA",
        excerpt:
          "Collect the order ID and a photo, then create the RMA through the returns webhook before promising anything.",
        status: "published",
        updatedAt: "2026-08-11",
      },
      {
        id: "late-return",
        title: "Return requested after the window closed",
        excerpt:
          "Escalate to a human. Do not commit to an exception on the agent's own authority.",
        status: "draft",
        updatedAt: "2026-08-28",
      },
    ],
  },
  {
    id: "technical-support",
    name: "Technical Support",
    articles: [
      {
        id: "webhook-signature",
        title: "Customer reports webhook signature mismatch",
        excerpt:
          "Walk through the raw-body requirement first — it is the cause roughly nine times in ten.",
        status: "published",
        updatedAt: "2026-08-22",
      },
      {
        id: "saml-setup",
        title: "SAML metadata rejected during SSO setup",
        excerpt:
          "The field wants raw XML, not the Okta metadata URL. Send the paste-the-XML instructions.",
        status: "ready",
        updatedAt: "2026-08-29",
      },
    ],
  },
];

const external: KbCategory[] = [];

export const internalSuggestions = ["Billing", "Returns", "Technical Support"];

export const externalSuggestions = [
  "Getting Started",
  "Account & Billing",
  "FAQs",
  "Shipping & Returns",
  "Troubleshooting",
];

export const sourceModes = [
  { id: "manual", label: "Manual" },
  { id: "url", label: "Sync from URL" },
  { id: "upload", label: "Upload documents" },
];

export async function getKnowledgeBase(
  scope: "internal" | "external",
): Promise<KbCategory[]> {
  return scope === "internal" ? internal : external;
}

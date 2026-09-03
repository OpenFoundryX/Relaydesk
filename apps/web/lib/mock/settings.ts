import type {
  ApiKey,
  ChannelAccount,
  ImportSource,
  Integration,
  McpServer,
  Plan,
  Snippet,
  TeamMember,
  Webhook,
} from "./types";

const snippets: Snippet[] = [
  {
    id: "follow-up",
    title: "Follow up",
    content:
      "Just checking in — were you able to resolve this, or is there anything else I can help with?",
  },
  {
    id: "greeting",
    title: "Greeting",
    content: "Hi {{customer.first_name}}, thanks for reaching out! How can I help today?",
  },
  {
    id: "issue-resolved",
    title: "Issue resolved",
    content:
      "Glad we could get this sorted out. If anything else comes up, don't hesitate to reply here.",
  },
  {
    id: "request-more-info",
    title: "Request more info",
    content:
      "Could you provide a bit more detail so I can look into this further? Specifically, the order ID and roughly when it happened.",
  },
  {
    id: "thank-you",
    title: "Thank you",
    content: "Thank you for your patience — I appreciate you working through this with me.",
  },
];

const snippetVariables = [
  "{{customer.first_name}}",
  "{{customer.email}}",
  "{{ticket.id}}",
  "{{ticket.subject}}",
  "{{agent.name}}",
  "{{workspace.name}}",
];

const apiKeys: ApiKey[] = [
  {
    id: "key_live_1",
    name: "Production ingest",
    prefix: "rd_live_7f2a",
    createdAt: "2026-07-14",
    lastUsedAt: "2026-08-30",
  },
  {
    id: "key_test_1",
    name: "Staging",
    prefix: "rd_test_be91",
    createdAt: "2026-08-02",
    lastUsedAt: null,
  },
];

const webhooks: Webhook[] = [
  {
    id: "wh_refund",
    name: "refund_order",
    description: "Refunds an order by its order_id.",
    method: "POST",
    url: "https://api.example.com/relaydesk/refund",
    params: [
      { name: "order_id", type: "string", description: "The order to refund.", required: true },
      { name: "amount", type: "number", description: "Partial amount in cents.", required: false },
    ],
  },
  {
    id: "wh_lookup",
    name: "lookup_subscription",
    description: "Returns the caller's current plan and renewal date.",
    method: "GET",
    url: "https://api.example.com/relaydesk/subscription",
    params: [
      { name: "email", type: "string", description: "Customer email address.", required: true },
    ],
  },
];

const mcpServers: McpServer[] = [
  {
    id: "mcp_support",
    name: "Support MCP Server",
    description: "Customer lookup and account tools",
    url: "https://mcp.example.com/mcp",
    active: true,
    toolCount: 6,
  },
];

const integrations: Integration[] = [
  { id: "slack", name: "Slack", category: "Notifications", monogram: "SL", connected: true },
  { id: "stripe", name: "Stripe", category: "Payments", monogram: "ST", connected: true },
  { id: "revenuecat", name: "RevenueCat", category: "Payments", monogram: "RC", connected: false },
  { id: "shopify", name: "Shopify", category: "Payments", monogram: "SH", connected: false },
  { id: "google-play", name: "Google Play", category: "Payments", monogram: "GP", connected: false },
  { id: "paypal", name: "PayPal", category: "Payments", monogram: "PP", connected: false },
  { id: "square", name: "Square", category: "Payments", monogram: "SQ", connected: false },
  { id: "paddle", name: "Paddle", category: "Payments", monogram: "PD", connected: false },
  { id: "mongodb", name: "MongoDB", category: "Data", monogram: "MG", connected: false },
  { id: "supabase", name: "Supabase", category: "Data", monogram: "SB", connected: true },
  { id: "postgresql", name: "PostgreSQL", category: "Data", monogram: "PG", connected: false },
  { id: "mysql", name: "MySQL", category: "Data", monogram: "MY", connected: false },
  { id: "convex", name: "Convex", category: "Data", monogram: "CV", connected: false },
  { id: "snowflake", name: "Snowflake", category: "Data", monogram: "SF", connected: false },
  { id: "dynamodb", name: "DynamoDB", category: "Data", monogram: "DD", connected: false },
  { id: "firebase", name: "Firebase", category: "Data", monogram: "FB", connected: false },
  { id: "github", name: "GitHub", category: "Development", monogram: "GH", connected: true },
  { id: "linear", name: "Linear", category: "Development", monogram: "LN", connected: false },
  { id: "jira", name: "Jira", category: "Development", monogram: "JR", connected: false },
  { id: "asana", name: "Asana", category: "Development", monogram: "AS", connected: false },
];

const team: TeamMember[] = [
  {
    id: "u_nilesh",
    name: "Nilesh Pant",
    email: "nilesh@relaydesk.dev",
    role: "Admin",
    status: "active",
  },
  {
    id: "u_sara",
    name: "Sara Duval",
    email: "sara@relaydesk.dev",
    role: "Agent",
    status: "active",
  },
  {
    id: "u_jonah",
    name: "Jonah Adeyemi",
    email: "jonah@relaydesk.dev",
    role: "Agent",
    status: "invited",
  },
];

const plans: Plan[] = [
  {
    id: "starter",
    name: "Starter",
    price: "$50",
    cadence: "per month",
    blurb: "For teams taking support seriously for the first time.",
    cta: "Choose Starter",
    featured: false,
    features: [
      "3 seats",
      "300 tickets / month",
      "Connect your database and Stripe",
      "One unified inbox across channels",
    ],
  },
  {
    id: "growth",
    name: "Growth",
    price: "$200",
    cadence: "per month for",
    blurb: "For teams where support volume is climbing fast.",
    cta: "Choose Growth",
    featured: true,
    meteredOptions: ["1,000 tickets / month", "2,500 tickets / month", "5,000 tickets / month"],
    features: [
      "10 seats",
      "1,000 tickets / month",
      "Every channel and integration",
      "Priority support",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "Let's talk",
    cadence: "",
    blurb: "For teams with procurement, and a security review.",
    cta: "Contact sales",
    featured: false,
    features: [
      "Custom seats",
      "3,000+ tickets / month",
      "SSO and SAML",
      "A named account manager",
    ],
  },
];

const emailAccounts: ChannelAccount[] = [
  {
    id: "ch_support",
    kind: "email",
    label: "support@relaydesk.dev",
    detail: "Gmail · syncing",
  },
];

const discordAccounts: ChannelAccount[] = [];

const importSources: ImportSource[] = [
  { id: "freshdesk", name: "Freshdesk", host: "*.freshdesk.com", monogram: "FD", comingSoon: false },
  { id: "zendesk", name: "Zendesk", host: "*.zendesk.com", monogram: "ZD", comingSoon: false },
  { id: "helpscout", name: "Help Scout", host: "api.helpscout.net", monogram: "HS", comingSoon: false },
  { id: "zohodesk", name: "Zoho Desk", host: "*.zohodesk.com", monogram: "ZO", comingSoon: true },
];

export const triageDefaults = {
  priority: `Set @URGENT for outages, security issues, or any message containing "down"
Set @HIGH for paying customers reporting a broken feature
Set @MEDIUM for general product questions
Set @LOW for feature requests and feedback`,
  assignee: `Billing questions → assign to @Sara
Technical issues → assign to @Nilesh
Enterprise customers → assign to @Sara
Anything marked urgent → assign to @Nilesh`,
};

export const timeZones = [
  "Asia/Calcutta  GMT+5:30",
  "Europe/London  GMT+1:00",
  "America/New_York  GMT-4:00",
  "America/Los_Angeles  GMT-7:00",
  "Australia/Sydney  GMT+10:00",
];

export async function getSnippets(): Promise<Snippet[]> {
  return snippets;
}
export async function getSnippetVariables(): Promise<string[]> {
  return snippetVariables;
}
export async function getApiKeys(): Promise<ApiKey[]> {
  return apiKeys;
}
export async function getWebhooks(): Promise<Webhook[]> {
  return webhooks;
}
export async function getMcpServers(): Promise<McpServer[]> {
  return mcpServers;
}
export async function getIntegrations(): Promise<Integration[]> {
  return integrations;
}
export async function getTeam(): Promise<TeamMember[]> {
  return team;
}
export async function getPlans(): Promise<Plan[]> {
  return plans;
}
export async function getEmailAccounts(): Promise<ChannelAccount[]> {
  return emailAccounts;
}
export async function getDiscordAccounts(): Promise<ChannelAccount[]> {
  return discordAccounts;
}
export async function getImportSources(): Promise<ImportSource[]> {
  return importSources;
}

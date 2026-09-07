import type {
  DiscordAccount,
  ImportSource,
  Integration,
  McpServer,
  Plan,
  Snippet,
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
  { id: "slack", brand: "slack", name: "Slack", category: "Notifications", monogram: "SL", connected: true },
  { id: "stripe", brand: "stripe", name: "Stripe", category: "Payments", monogram: "ST", connected: true },
  { id: "revenuecat", brand: "revenuecat", name: "RevenueCat", category: "Payments", monogram: "RC", connected: false },
  { id: "shopify", brand: "shopify", name: "Shopify", category: "Payments", monogram: "SH", connected: false },
  { id: "google-play", brand: "googleplay", name: "Google Play", category: "Payments", monogram: "GP", connected: false },
  { id: "paypal", brand: "paypal", name: "PayPal", category: "Payments", monogram: "PP", connected: false },
  { id: "square", brand: "square", name: "Square", category: "Payments", monogram: "SQ", connected: false },
  { id: "paddle", brand: "paddle", name: "Paddle", category: "Payments", monogram: "PD", connected: false },
  { id: "mongodb", brand: "mongodb", name: "MongoDB", category: "Data", monogram: "MG", connected: false },
  { id: "supabase", brand: "supabase", name: "Supabase", category: "Data", monogram: "SB", connected: true },
  { id: "postgresql", brand: "postgresql", name: "PostgreSQL", category: "Data", monogram: "PG", connected: false },
  { id: "mysql", brand: "mysql", name: "MySQL", category: "Data", monogram: "MY", connected: false },
  { id: "convex", brand: "convex", name: "Convex", category: "Data", monogram: "CV", connected: false },
  { id: "snowflake", brand: "snowflake", name: "Snowflake", category: "Data", monogram: "SF", connected: false },
  { id: "dynamodb", name: "DynamoDB", category: "Data", monogram: "DD", connected: false },
  { id: "firebase", brand: "firebase", name: "Firebase", category: "Data", monogram: "FB", connected: false },
  { id: "github", brand: "github", name: "GitHub", category: "Development", monogram: "GH", connected: true },
  { id: "linear", brand: "linear", name: "Linear", category: "Development", monogram: "LN", connected: false },
  { id: "jira", brand: "jira", name: "Jira", category: "Development", monogram: "JR", connected: false },
  { id: "asana", brand: "asana", name: "Asana", category: "Development", monogram: "AS", connected: false },
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

const discordAccounts: DiscordAccount[] = [];

const importSources: ImportSource[] = [
  { id: "freshdesk", name: "Freshdesk", host: "*.freshdesk.com", monogram: "FD", comingSoon: false },
  { id: "zendesk", brand: "zendesk", name: "Zendesk", host: "*.zendesk.com", monogram: "ZD", comingSoon: false },
  { id: "helpscout", brand: "helpscout", name: "Help Scout", host: "api.helpscout.net", monogram: "HS", comingSoon: false },
  { id: "zohodesk", brand: "zoho", name: "Zoho Desk", host: "*.zohodesk.com", monogram: "ZO", comingSoon: true },
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

export async function getSnippets(): Promise<Snippet[]> {
  return snippets;
}
export async function getSnippetVariables(): Promise<string[]> {
  return snippetVariables;
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
export async function getPlans(): Promise<Plan[]> {
  return plans;
}
export async function getDiscordAccounts(): Promise<DiscordAccount[]> {
  return discordAccounts;
}
export async function getImportSources(): Promise<ImportSource[]> {
  return importSources;
}

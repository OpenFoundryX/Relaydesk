import type { PortalSettings, SetupTask } from "./types";

export const workspace = {
  name: "Chronon",
  monogram: "CH",
  plan: "Starter",
  trialDaysLeft: 6,
  ticketsThisPeriod: 412,
  projectedTickets: 480,
  seats: 2,
};

export const currentUser = {
  name: "Nilesh Pant",
  email: "nilesh@relaydesk.dev",
  monogram: "NP",
  timeZone: "Asia/Calcutta  GMT+5:30",
  emailNotifications: false,
  slackNotifications: false,
};

const setupTasks: SetupTask[] = [
  { id: "channel", label: "Connect a channel", href: "/settings/channels", done: true },
  { id: "team", label: "Invite your team", href: "/settings/team", done: true },
  { id: "integrations", label: "Connect an integration", href: "/settings/integrations", done: true },
  { id: "kb", label: "Write your first internal article", href: "/knowledge-base", done: true },
  { id: "portal", label: "Launch your user portal", href: "/user-portal/general", done: false },
  { id: "triage", label: "Turn on AI triage", href: "/settings/ai-triage", done: false },
  { id: "billing", label: "Choose a plan", href: "/settings/billing", done: false },
];

const portal: PortalSettings = {
  name: "Chronon",
  subdomain: "chronon-0ifh2x",
  domain: "relaydesk.app",
  status: "deployed",
  headline: "Submit a ticket",
  intro: "Need help? Send the Chronon team a note and we'll come back to you.",
  accent: "#18181B",
};

export async function getSetupTasks(): Promise<SetupTask[]> {
  return setupTasks;
}

export async function getPortalSettings(): Promise<PortalSettings> {
  return portal;
}

import type { PortalSettings } from "../types";

const portal: PortalSettings = {
  name: "Chronon",
  subdomain: "chronon-0ifh2x",
  domain: "relaydesk.app",
  status: "deployed",
  headline: "Submit a ticket",
  intro: "Need help? Send the Chronon team a note and we'll come back to you.",
  accent: "#18181B",
};

export async function getPortalSettings(): Promise<PortalSettings> {
  return portal;
}

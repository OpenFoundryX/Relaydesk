import { Server } from "lucide-react";

import { PageHeader } from "@/components/console/page-header";
import { SectionEmpty, SettingSection } from "@/components/console/setting-section";
import { McpServerDialog } from "@/components/settings/mcp-server-dialog";
import { Badge } from "@/components/ui/badge";
import { getMcpServers } from "@/lib/mock/settings";

export const metadata = { title: "MCP servers" };

export default async function McpServersPage() {
  const servers = await getMcpServers();

  return (
    <>
      <PageHeader
        title="MCP servers"
        description="Give the agent tools from any Model Context Protocol server you run."
      />

      <SettingSection
        title="Servers"
        description="Tools are re-discovered each time a conversation starts."
        action={<McpServerDialog />}
      >
        {servers.length > 0 ? (
          <ul className="divide-y divide-ink-200 rounded-md border border-ink-200">
            {servers.map((server) => (
              <li key={server.id} className="flex items-center gap-3 px-3 py-3">
                <Server className="size-4 shrink-0 text-ink-400" />
                <div className="min-w-0">
                  <p className="text-[13px] font-medium text-ink-900">
                    {server.name}
                  </p>
                  <p className="truncate font-mono text-[11px] text-ink-400">
                    {server.url}
                  </p>
                </div>
                <span className="ml-auto shrink-0 text-[12px] text-ink-500">
                  {server.toolCount} tools
                </span>
                <Badge variant={server.active ? "positive" : "neutral"}>
                  {server.active ? "Active" : "Paused"}
                </Badge>
              </li>
            ))}
          </ul>
        ) : (
          <SectionEmpty>No MCP servers yet</SectionEmpty>
        )}
      </SettingSection>
    </>
  );
}

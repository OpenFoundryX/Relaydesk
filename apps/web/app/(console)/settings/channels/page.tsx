import { Download, Mail, MessageSquare, Webhook } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/console/page-header";
import { SectionEmpty, SettingSection } from "@/components/console/setting-section";
import { BrandIcon } from "@/components/brand-icons";
import { AddChannelDialog } from "@/components/settings/add-channel-dialog";
import { EmailChannelActions } from "@/components/settings/email-channel-actions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getEmailChannels } from "@/lib/api/channels";
import { getDiscordAccounts, getImportSources } from "@/lib/mock/settings";

export const metadata = { title: "Channels" };

export default async function ChannelsPage() {
  const [emailChannels, discordAccounts, importSources] = await Promise.all([
    getEmailChannels(),
    getDiscordAccounts(),
    getImportSources(),
  ]);

  return (
    <>
      <PageHeader
        title="Channels"
        description="Where tickets come into Relaydesk from."
      />

      <div className="space-y-4">
        <SettingSection
          title="Email"
          description="Mail sent to a connected address turns into a ticket automatically."
          action={<AddChannelDialog />}
        >
          {emailChannels.length > 0 ? (
            <div className="space-y-3">
              <ul className="divide-y divide-ink-200 rounded-md border border-ink-200">
                {emailChannels.map((channel) => (
                  <li
                    key={channel.id}
                    className="flex items-center gap-3 px-3 py-2.5"
                  >
                    <Mail className="size-4 shrink-0 text-ink-400" />
                    <div className="min-w-0">
                      <p className="truncate font-mono text-[13px] font-medium text-ink-900">
                        {channel.address}
                      </p>
                      <p className="truncate text-[12px] text-ink-500">
                        {channel.displayName}
                      </p>
                    </div>
                    <EmailChannelActions channel={channel} />
                  </li>
                ))}
              </ul>
              <p className="text-[12px] leading-relaxed text-ink-500">
                Forward mail from your own support address to this one. Anything that
                arrives becomes a ticket.
              </p>
            </div>
          ) : (
            <SectionEmpty>No connected addresses</SectionEmpty>
          )}
        </SettingSection>

        <SettingSection
          title="Discord"
          description="Posts in a Discord forum channel turn into tickets automatically."
          action={
            <Button variant="primary" size="sm">
              <MessageSquare />
              Connect Discord
            </Button>
          }
        >
          {discordAccounts.length > 0 ? (
            <ul>
              {discordAccounts.map((account) => (
                <li key={account.id}>{account.label}</li>
              ))}
            </ul>
          ) : (
            <SectionEmpty>No connected servers</SectionEmpty>
          )}
        </SettingSection>

        <SettingSection
          title="One-click import"
          description="Bring contacts, tickets, and canned replies over from another help desk."
        >
          <div className="grid gap-2 sm:grid-cols-2">
            {importSources.map((source) => (
              <div
                key={source.id}
                className="flex items-center gap-3 rounded-md border border-ink-200 px-3 py-2.5"
              >
                <span className="inline-flex size-7 shrink-0 items-center justify-center rounded bg-ink-100 font-mono text-[10px] font-semibold text-ink-500">
                  {source.brand ? (
                    <BrandIcon brand={source.brand} className="size-4" />
                  ) : (
                    source.monogram
                  )}
                </span>
                <div className="min-w-0">
                  <p className="flex items-center gap-1.5 text-[13px] font-medium text-ink-900">
                    {source.name}
                    {source.comingSoon && (
                      <Badge variant="outline">Coming soon</Badge>
                    )}
                  </p>
                  <p className="truncate font-mono text-[11px] text-ink-400">
                    {source.host}
                  </p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  className="ml-auto"
                  disabled={source.comingSoon}
                >
                  <Download />
                  Import
                </Button>
              </div>
            ))}
          </div>
        </SettingSection>

        <SettingSection
          title="API"
          description="Create tickets from your own systems with the Relaydesk API."
          action={
            <Button asChild variant="secondary" size="sm">
              <Link href="/settings/api-keys">
                <Webhook />
                Manage API keys
              </Link>
            </Button>
          }
        />
      </div>
    </>
  );
}

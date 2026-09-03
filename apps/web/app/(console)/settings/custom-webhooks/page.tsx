import { PageHeader } from "@/components/console/page-header";
import { SectionEmpty, SettingSection } from "@/components/console/setting-section";
import { Badge } from "@/components/ui/badge";
import { WebhookDialog } from "@/components/settings/webhook-dialog";
import { getWebhooks } from "@/lib/mock/settings";

export const metadata = { title: "Custom webhooks" };

export default async function CustomWebhooksPage() {
  const webhooks = await getWebhooks();

  return (
    <>
      <PageHeader
        title="Custom webhooks"
        description="Register endpoints you control as tools the agent can call. Every request is signed with your webhook secret."
      />

      <SettingSection
        title="Webhooks"
        description="The agent picks a tool by reading its description, so write them carefully."
        action={<WebhookDialog />}
      >
        {webhooks.length > 0 ? (
          <ul className="divide-y divide-ink-200 rounded-md border border-ink-200">
            {webhooks.map((webhook) => (
              <li key={webhook.id} className="px-3 py-3">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="font-mono">
                    {webhook.method}
                  </Badge>
                  <span className="font-mono text-[13px] font-medium text-ink-900">
                    {webhook.name}
                  </span>
                  <span className="ml-auto truncate font-mono text-[11px] text-ink-400">
                    {webhook.url}
                  </span>
                </div>
                <p className="mt-1 text-[13px] text-ink-500">{webhook.description}</p>
                {webhook.params.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {webhook.params.map((param) => (
                      <span
                        key={param.name}
                        className="rounded border border-ink-200 bg-ink-50 px-1.5 py-0.5 font-mono text-[11px] text-ink-600"
                      >
                        {param.name}
                        <span className="text-ink-400">:{param.type}</span>
                        {param.required && <span className="text-accent-800">*</span>}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <SectionEmpty>No webhooks yet</SectionEmpty>
        )}
      </SettingSection>
    </>
  );
}

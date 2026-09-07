import { KeyRound } from "lucide-react";

import { PageHeader } from "@/components/console/page-header";
import { SectionEmpty, SettingSection } from "@/components/console/setting-section";
import { ApiKeyDialog } from "@/components/settings/api-key-dialog";
import { CodeSample } from "@/components/settings/code-sample";
import { getApiKeys } from "@/lib/mock/settings";
import { requireAdmin } from "@/lib/api/workspace";

export const metadata = { title: "API keys" };

export default async function ApiKeysPage() {
  await requireAdmin();

  const keys = await getApiKeys();

  return (
    <>
      <PageHeader
        title="API keys"
        description="Create tickets from your own systems, or import conversations from another platform."
      />

      <div className="space-y-4">
        <SettingSection
          title="Keys"
          description="Rotate a key by creating a new one, then deleting the old one."
          action={<ApiKeyDialog />}
        >
          {keys.length > 0 ? (
            <ul className="divide-y divide-ink-200 rounded-md border border-ink-200">
              {keys.map((key) => (
                <li key={key.id} className="flex items-center gap-3 px-3 py-2.5">
                  <KeyRound className="size-4 shrink-0 text-ink-400" />
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium text-ink-900">{key.name}</p>
                    <p className="font-mono text-[11px] text-ink-400">
                      {key.prefix}···
                    </p>
                  </div>
                  <span className="tabular ml-auto shrink-0 text-[12px] text-ink-500">
                    {key.lastUsedAt
                      ? `Last used ${key.lastUsedAt}`
                      : "Never used"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <SectionEmpty>No API keys yet</SectionEmpty>
          )}
        </SettingSection>

        <SettingSection
          title="Create a conversation"
          description="POST /v1/conversations — customer_email and message are required; everything else is optional."
        >
          <CodeSample />
        </SettingSection>
      </div>
    </>
  );
}

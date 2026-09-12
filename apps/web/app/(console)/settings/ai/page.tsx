import { PageHeader } from "@/components/console/page-header";
import { AiSettings } from "@/components/settings/ai-settings";
import { getAiConfig } from "@/lib/api/ai-config";
import { requireAdmin } from "@/lib/api/workspace";

export const metadata = { title: "AI answers" };

export default async function AiSettingsPage() {
  await requireAdmin();

  const config = await getAiConfig();

  return (
    <>
      <PageHeader
        title="AI answers"
        description="Let the widget answer questions itself, drawn from your knowledge base, before a visitor ever reaches an agent."
      />

      <AiSettings config={config} />
    </>
  );
}

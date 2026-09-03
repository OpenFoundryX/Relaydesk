import { PageHeader } from "@/components/console/page-header";
import { TriageSettings } from "@/components/settings/triage-settings";
import { triageDefaults } from "@/lib/mock/settings";

export const metadata = { title: "AI triage" };

export default function AiTriagePage() {
  return (
    <>
      <PageHeader
        title="AI triage"
        description="Written in plain language, applied to every message the moment it lands."
      />
      <TriageSettings defaults={triageDefaults} />
    </>
  );
}

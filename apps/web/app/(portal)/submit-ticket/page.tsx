import { SubmitTicketForm } from "@/components/portal/submit-ticket-form";
import { getPortalSettings } from "@/lib/mock/workspace";

export const metadata = { title: "Submit a ticket" };

export default async function SubmitTicketPage() {
  const portal = await getPortalSettings();

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
        {portal.headline}
      </h1>
      <p className="mt-1.5 text-[15px] leading-relaxed text-ink-500">
        {portal.intro}
      </p>

      <div className="mt-8">
        <SubmitTicketForm workspaceName={portal.name} />
      </div>
    </main>
  );
}

import { PageHeader } from "@/components/console/page-header";
import { PortalActions } from "@/components/portal/portal-actions";
import { TicketFormSettings } from "@/components/portal/ticket-form-settings";

export const metadata = { title: "Portal · Ticket form" };

export default function PortalTicketFormPage() {
  return (
    <>
      <PageHeader
        title="Ticket form"
        description="What customers fill in when they submit a ticket."
        actions={<PortalActions />}
      />
      <TicketFormSettings />
    </>
  );
}

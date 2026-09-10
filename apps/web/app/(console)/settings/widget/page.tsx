import { PageHeader } from "@/components/console/page-header";
import { NewWidgetKeyButton } from "@/components/settings/widget-key-dialog";
import { WidgetKeyActions } from "@/components/settings/widget-key-actions";
import { WidgetKeys } from "@/components/settings/widget-keys";
import { getWidgetKeys } from "@/lib/api/widget-keys";
import { requireAdmin } from "@/lib/api/workspace";

export const metadata = { title: "Widget" };

export default async function WidgetPage() {
  await requireAdmin();

  const keys = await getWidgetKeys();

  return (
    <>
      <PageHeader
        title="Widget"
        description="Embed self-serve help and a way to reach you on any site with a single script tag."
        actions={<NewWidgetKeyButton />}
      />

      <WidgetKeys
        keys={keys}
        renderActions={(key) => <WidgetKeyActions widgetKey={key} />}
      />
    </>
  );
}

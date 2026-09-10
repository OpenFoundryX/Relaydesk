import { notFound } from "next/navigation";

import { submitWidgetTicketAction } from "@/app/(widget)/widget/frame/actions";
import { Panel } from "@/components/widget/panel";
import { getWidgetBootstrap } from "@/lib/api/widget";

/**
 * The panel a visitor actually sees, served inside the loader's iframe
 * (spec D5). Reached at `/widget/frame?key=rdw_…` -- key, never slug (spec
 * D3), so a workspace can rename itself without every customer re-pasting a
 * script tag.
 *
 * This route sends no `Content-Security-Policy` header itself: a Server
 * Component cannot set one, and it is per-key, so `middleware.ts` sets it
 * instead -- see the `pathname === "/widget/frame"` branch there.
 */
export default async function WidgetFramePage({
  searchParams,
}: {
  searchParams: Promise<{ key?: string }>;
}) {
  const { key } = await searchParams;
  if (!key) notFound();

  const bootstrap = await getWidgetBootstrap(key);
  if (!bootstrap) notFound();

  return (
    <Panel
      {...bootstrap}
      widgetKey={key}
      onSubmit={submitWidgetTicketAction.bind(null, key)}
    />
  );
}

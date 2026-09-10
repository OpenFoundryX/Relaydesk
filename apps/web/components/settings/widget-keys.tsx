import type { ReactNode } from "react";

import { SectionEmpty, SettingSection } from "@/components/console/setting-section";
import type { WidgetKey, WidgetKeySettings } from "@/lib/api/widget-keys";

// The console's own configured URL, not a fixed relaydesk.dev domain --
// `lib/api/portal.ts` establishes the same WEB_URL ?? NEXT_PUBLIC_WEB_URL
// idiom. This is how the widget.js loader (apps/web/public/widget.js) is
// served: same origin as the console. Getting this wrong hands a
// self-hosted install's admin, per the README, a snippet pointing at a
// domain they do not control.
const WEB_URL =
  process.env.WEB_URL ?? process.env.NEXT_PUBLIC_WEB_URL ?? "http://localhost:3000";

/**
 * `data-accent` and `data-position` are read by the loader before it draws
 * the launcher (spec D6/D10) -- omitted entirely when unconfigured, so an
 * embed with no branding gets exactly today's `<script>` tag, unchanged.
 * `position` is included only when it is `"left"`: `"right"` is the
 * loader's own fallback, so leaving it out there is what an absent setting
 * already means.
 */
function snippet(key: string, settings: WidgetKeySettings): string {
  const attrs = [`data-key="${key}"`];
  if (settings.accentColour) attrs.push(`data-accent="${settings.accentColour}"`);
  if (settings.position === "left") attrs.push(`data-position="left"`);
  return `<script async src="${WEB_URL}/widget.js" ${attrs.join(" ")}></script>`;
}

/**
 * Settings → Widget: one card per embed, each with its snippet and its
 * allowlist.
 *
 * Purely presentational -- it never imports the row controls itself. Those
 * (`WidgetKeyActions`, a "use client" component that calls server actions)
 * are handed in per row via `renderActions` instead, so this component and
 * its test stay free of that chain. Compare `SnippetActions`, which webhooks
 * and snippets both keep as a sibling for the same reason.
 *
 * Two things the copy here carries because both are silent failures
 * otherwise: the key is public and belongs in page source (the opposite of
 * the API key on the neighbouring `/settings/api-keys` screen, whose secret
 * must never be pasted into a page), and an empty allowlist refuses rather
 * than permits -- a finished-looking snippet with nothing listed here will
 * not load anywhere, and this is the only place that gets explained.
 *
 * The snippet reflects `settings` (spec D10): `data-accent` and
 * `data-position` are added when configured, because the loader (D6) reads
 * the launcher's colour and corner from the tag itself, before the panel's
 * first open -- see `public/widget.js`. Editing name, greeting and the rest
 * happens in `WidgetKeyDialog`; this component only ever renders the result.
 */
export function WidgetKeys({
  keys,
  renderActions,
}: {
  keys: WidgetKey[];
  renderActions?: (key: WidgetKey) => ReactNode;
}) {
  if (keys.length === 0) {
    return <SectionEmpty>No embeds yet</SectionEmpty>;
  }

  return (
    <div className="flex flex-col gap-4">
      {keys.map((embed) => (
        <SettingSection
          key={embed.id}
          title={embed.name}
          action={renderActions?.(embed)}
        >
          <pre className="overflow-x-auto rounded-md border border-ink-200 bg-ink-50 p-3 text-[13px] text-ink-700">
            {snippet(embed.key, embed.settings)}
          </pre>
          <p className="mt-2 text-[13px] text-ink-500">
            This key is public. It appears in the source of every page that
            embeds the widget, so it is safe to paste there -- unlike an API
            key, which must never be.
          </p>
          <p className="mt-2 text-[13px] text-ink-500">
            The launcher&apos;s colour and position live in this snippet, not
            in the panel it opens. Changing either one under Branding takes
            effect only once you re-paste the updated snippet wherever this
            embed is installed.
          </p>

          {embed.allowedOrigins.length === 0 ? (
            <p className="mt-3 text-[13px] text-danger-700">
              Add the sites allowed to show this widget -- until you do, it
              will not load anywhere.
            </p>
          ) : (
            <ul className="mt-3 flex flex-col gap-1 font-mono text-[13px] text-ink-700">
              {embed.allowedOrigins.map((origin) => (
                <li key={origin}>{origin}</li>
              ))}
            </ul>
          )}

          <p className="mt-3 text-[12px] text-ink-400">
            {embed.active ? "Active" : "Deactivated"} ·{" "}
            {embed.lastSeenAt
              ? `Last seen ${new Date(embed.lastSeenAt).toLocaleDateString()}`
              : "Never seen"}
          </p>
        </SettingSection>
      ))}
    </div>
  );
}

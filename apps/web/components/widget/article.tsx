"use client";

import { useEffect, useState } from "react";

import { WidgetButton } from "@/components/widget/button";
import { DocRenderer } from "@/components/knowledge-base/doc-renderer";
import type { WidgetArticle } from "@/lib/api/widget";

// A widget key never exposes a slug (spec D3), and the panel has no route
// of its own to serve an inline image by id -- so an article's images do
// not render here. This is a v1 gap, not a silent failure: the doc still
// renders text, headings and links, and the reader can always read the
// same article, images included, on the workspace's own help site.
const NO_IMAGE = "";

/**
 * One article, read inline. "Send a message" is primary at its foot, for
 * the same reason it is primary on Results: the visitor has tried to
 * self-serve (design §7).
 */
export function Article({
  widgetKey,
  path,
  onCompose,
}: {
  widgetKey: string | undefined;
  path: string;
  onCompose: () => void;
}) {
  // See results.tsx for why this resets by remounting (keyed on `path` in
  // panel.tsx) rather than by clearing state synchronously in the effect.
  const [article, setArticle] = useState<WidgetArticle | null | "loading">("loading");

  useEffect(() => {
    let cancelled = false;
    const request = widgetKey
      ? fetch(
          `/widget/kb/article?key=${encodeURIComponent(widgetKey)}&path=${encodeURIComponent(path)}`,
        ).then((response) => (response.ok ? response.json() : null))
      : Promise.resolve(null);
    request
      .then((found: WidgetArticle | null) => {
        if (!cancelled) setArticle(found);
      })
      .catch(() => {
        if (!cancelled) setArticle(null);
      });
    return () => {
      cancelled = true;
    };
  }, [widgetKey, path]);

  return (
    <div className="flex flex-1 flex-col gap-4 px-4 py-6">
      {article === "loading" && <p className="text-[13px] text-ink-400">Loading…</p>}

      {article === null && (
        <p className="text-[13px] text-ink-500 dark:text-ink-400">
          That article could not be found.
        </p>
      )}

      {article && article !== "loading" && (
        <article>
          <h1 className="text-[16px] font-semibold tracking-tight text-ink-900 dark:text-white">
            {article.title}
          </h1>
          {article.excerpt && (
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink-500 dark:text-ink-400">
              {article.excerpt}
            </p>
          )}
          <div className="mt-4 text-[13px] leading-relaxed text-ink-800 dark:text-ink-200 [&_h2]:mt-5 [&_h2]:text-[14px] [&_h2]:font-semibold [&_h2]:text-ink-900 [&_h2]:dark:text-white [&_h3]:mt-4 [&_h3]:text-[13px] [&_h3]:font-semibold [&_p]:my-2.5 [&_ul]:my-2.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2.5 [&_ol]:list-decimal [&_ol]:pl-5 [&_a]:text-accent-950 [&_a]:underline [&_a]:dark:text-accent-400">
            <DocRenderer doc={article.doc} imageSrc={() => NO_IMAGE} />
          </div>
        </article>
      )}

      <div className="mt-auto pt-2">
        <WidgetButton type="button" variant="primary" onClick={onCompose}>
          Send a message
        </WidgetButton>
      </div>
    </div>
  );
}

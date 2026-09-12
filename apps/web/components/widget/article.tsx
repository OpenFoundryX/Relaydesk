"use client";

import { useEffect, useState } from "react";

import { WidgetButton } from "@/components/widget/button";
import { DocRenderer } from "@/components/knowledge-base/doc-renderer";
import { articleHeadings } from "@/components/portal/headings";
import type { WidgetArticle, WidgetArticleSummary, WidgetCrumb } from "@/lib/api/widget";

// A widget key never exposes a slug (spec D3), and the panel has no route
// of its own to serve an inline image by id -- so an article's images do
// not render here. This is a v1 gap, not a silent failure: the doc still
// renders text, headings and links, and the reader can always read the
// same article, images included, on the workspace's own help site.
const NO_IMAGE = "";

/**
 * Rendered on the visitor's own machine, not the server -- unlike the help
 * site's `ArticleView`, this is a client component with no request/response
 * boundary to render a date on the far side of. UTC is still pinned: the
 * date on an article is a property of the article, not of whichever visitor
 * happens to be reading it right now.
 */
const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

function formatted(value: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : DATE_FORMAT.format(date);
}

/** What `/widget/kb/article` answers with -- see `getWidgetArticle` in
 * `lib/api/widget.ts`. Declared loosely (not as `WidgetArticlePage`
 * directly) so a response that fails to match it -- an old shape, a proxy
 * error page -- degrades to "not found" rather than throwing. */
type ArticleResponse = { article?: WidgetArticle; ancestors?: WidgetCrumb[] } | null;

type Loaded = { article: WidgetArticle; ancestors: WidgetCrumb[] };

/**
 * One article, read inline: title, subtitle, byline, an optional table of
 * contents, the body, related articles from the same collection, and a way
 * out to the same article on the full help site. "Send a message" is
 * primary at its foot, for the same reason it is primary on Results: the
 * visitor has tried to self-serve (design §7).
 */
export function Article({
  widgetKey,
  path,
  onCompose,
  onOpen,
  onTitleChange,
}: {
  widgetKey: string | undefined;
  path: string;
  onCompose: () => void;
  /** Opens another article in this same screen -- used by "Related
   * articles" below. Its own back control returns wherever this article's
   * did, the same lateral move Results and a collection's own article list
   * already make. */
  onOpen: (path: string) => void;
  /**
   * Told the article's title once it is known, or `null` while loading or
   * on failure. `help.tsx` carries this up to the panel's own header,
   * alongside the full-height signal it already reports.
   */
  onTitleChange?: (title: string | null) => void;
}) {
  // See results.tsx for why this resets by remounting (keyed on `path` in
  // panel.tsx) rather than by clearing state synchronously in the effect.
  const [loaded, setLoaded] = useState<Loaded | null | "loading">("loading");

  useEffect(() => {
    let cancelled = false;
    const request = widgetKey
      ? fetch(
          `/widget/kb/article?key=${encodeURIComponent(widgetKey)}&path=${encodeURIComponent(path)}`,
        ).then((response) => (response.ok ? response.json() : null))
      : Promise.resolve(null);
    request
      .then((found: ArticleResponse) => {
        if (cancelled) return;
        setLoaded(found && found.article ? { article: found.article, ancestors: found.ancestors ?? [] } : null);
      })
      .catch(() => {
        if (!cancelled) setLoaded(null);
      });
    return () => {
      cancelled = true;
    };
  }, [widgetKey, path]);

  useEffect(() => {
    onTitleChange?.(loaded && loaded !== "loading" ? loaded.article.title : null);
  }, [loaded, onTitleChange]);

  const article = loaded && loaded !== "loading" ? loaded.article : null;
  const ancestors = loaded && loaded !== "loading" ? loaded.ancestors : [];

  const [related, setRelated] = useState<WidgetArticleSummary[] | null>(null);

  useEffect(() => {
    if (!widgetKey || !article || ancestors.length === 0) {
      setRelated(null);
      return;
    }
    let cancelled = false;
    // The nearest ancestor's own slug is only one segment; the request the
    // rest of the tab already reuses (`kb/collections`) needs the whole
    // path down to it, same as `HelpBreadcrumb` builds one segment's href
    // from every crumb up to and including it.
    const collectionPath = ancestors.map((crumb) => crumb.slug).join("/");
    const currentId = article.id;
    fetch(
      `/widget/kb/collections?key=${encodeURIComponent(widgetKey)}&path=${encodeURIComponent(collectionPath)}`,
    )
      .then((response) => (response.ok ? response.json() : null))
      .then((found: unknown) => {
        if (cancelled) return;
        const list =
          found && typeof found === "object" && Array.isArray((found as { articles?: unknown }).articles)
            ? (found as { articles: WidgetArticleSummary[] }).articles
            : [];
        setRelated(list.filter((candidate) => candidate.id !== currentId));
      })
      .catch(() => {
        if (!cancelled) setRelated([]);
      });
    return () => {
      cancelled = true;
    };
    // `article` and `ancestors` both come from `loaded`, which only changes
    // when the fetch above resolves -- keying on the primitive id is enough
    // and avoids re-running this from an `ancestors` array that is a fresh
    // reference every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [widgetKey, article?.id]);

  // Only when it says something a byline did not already say. Most
  // published articles have both, but a null `publishedAt` (nothing this
  // widget ever shows today, since only published articles reach it, but
  // the type still allows it) falls back to when it was last touched.
  const published = article ? formatted(article.publishedAt) ?? formatted(article.updatedAt) : null;

  // One pass over the document for both the contents list and the ids the
  // headings themselves render with -- see `articleHeadings`'s own
  // docstring for why that has to be one walk rather than two.
  const headings = article ? articleHeadings(article.doc) : { list: [], idFor: () => undefined };

  return (
    <div className="flex flex-1 flex-col gap-4 px-4 py-6">
      {loaded === "loading" && <p className="text-[13px] text-ink-400">Loading…</p>}

      {loaded === null && (
        <p className="text-[13px] text-ink-500 dark:text-ink-400">
          That article could not be found.
        </p>
      )}

      {article && (
        <article>
          <h1 className="text-[18px] font-semibold leading-snug tracking-tight text-ink-900 dark:text-white">
            {article.title}
          </h1>
          {article.excerpt && (
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink-500 dark:text-ink-400">
              {article.excerpt}
            </p>
          )}

          {(article.author || published) && (
            <div className="mt-3 flex items-center gap-2">
              {article.author && (
                <span
                  aria-hidden
                  className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent-600 text-[10px] font-semibold text-white"
                >
                  {article.author.monogram}
                </span>
              )}
              <span className="text-[12px] leading-tight text-ink-500 dark:text-ink-400">
                {article.author && (
                  <span className="text-ink-700 dark:text-ink-200">{article.author.name}</span>
                )}
                {article.author && published && " · "}
                {published && (
                  <time dateTime={article.publishedAt ?? article.updatedAt}>{published}</time>
                )}
              </span>
            </div>
          )}

          {/* A contents list with one row, or none, is furniture rather
              than navigation -- see `ArticleToc` (components/portal), whose
              own rule this repeats. A native `<details>` rather than that
              component's own `<nav>`: it is keyboard accessible with no
              script of our own, and its entries stay findable by the
              browser's own find-in-page while it is closed. */}
          {headings.list.length >= 2 && (
            <details className="mt-4 rounded-md border border-ink-200 bg-ink-50 px-3 py-2 dark:border-ink-700 dark:bg-ink-800/60">
              <summary className="cursor-pointer text-[12px] font-medium text-ink-700 dark:text-ink-200">
                Contents
              </summary>
              <nav aria-label="On this page" className="mt-2">
                <ul className="flex flex-col gap-1.5">
                  {headings.list.map((heading) => (
                    <li key={heading.id}>
                      <a
                        href={`#${heading.id}`}
                        className={
                          heading.level === 3
                            ? "block pl-3 text-[12px] text-ink-500 hover:text-ink-900 dark:text-ink-400 dark:hover:text-white"
                            : "block text-[12px] text-ink-500 hover:text-ink-900 dark:text-ink-400 dark:hover:text-white"
                        }
                      >
                        {heading.text}
                      </a>
                    </li>
                  ))}
                </ul>
              </nav>
            </details>
          )}

          <div className="mt-4 text-[13px] leading-relaxed text-ink-800 dark:text-ink-200 [&_h2]:mt-5 [&_h2]:scroll-mt-4 [&_h2]:text-[14px] [&_h2]:font-semibold [&_h2]:text-ink-900 [&_h2]:dark:text-white [&_h3]:mt-4 [&_h3]:scroll-mt-4 [&_h3]:text-[13px] [&_h3]:font-semibold [&_p]:my-2.5 [&_ul]:my-2.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2.5 [&_ol]:list-decimal [&_ol]:pl-5 [&_a]:text-accent-950 [&_a]:underline [&_a]:dark:text-accent-400">
            <DocRenderer doc={article.doc} imageSrc={() => NO_IMAGE} headingId={headings.idFor} />
          </div>
        </article>
      )}

      {related && related.length > 0 && (
        <div className="border-t border-ink-200 pt-4 dark:border-ink-700">
          <h2 className="text-[11px] font-semibold uppercase tracking-wide text-ink-400">
            Related articles
          </h2>
          <ul className="mt-2 flex flex-col gap-1">
            {related.map((candidate) => (
              <li key={candidate.id}>
                <button
                  type="button"
                  onClick={() => onOpen(candidate.path)}
                  className="block w-full rounded-lg border border-ink-200 bg-white p-3 text-left transition-colors hover:border-ink-300 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:border-ink-700 dark:bg-ink-800 dark:hover:bg-ink-700"
                >
                  <span className="block text-[13px] font-medium text-ink-900 dark:text-white">
                    {candidate.title}
                  </span>
                  {candidate.excerpt && (
                    <span className="mt-0.5 line-clamp-2 block text-[12px] text-ink-500 dark:text-ink-400">
                      {candidate.excerpt}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {article && (
        <p className="text-[12px] text-ink-400">
          <a
            href={`/help/${article.path}`}
            // The panel lives in the loader's iframe (spec D5), which has
            // no chrome and no way back -- see ask.tsx's citations for the
            // same reasoning. A same-frame navigation would replace the
            // widget with the help site and strand the visitor there.
            target="_blank"
            rel="noreferrer"
            className="underline hover:text-ink-700 dark:hover:text-ink-200"
          >
            Open in help center
          </a>
        </p>
      )}

      <div className="mt-auto pt-2">
        <WidgetButton type="button" variant="primary" onClick={onCompose}>
          Send a message
        </WidgetButton>
      </div>
    </div>
  );
}

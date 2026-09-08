import { DocRenderer } from "@/components/knowledge-base/doc-renderer";
import { ArticleToc } from "@/components/portal/article-toc";
import { articleHeadings } from "@/components/portal/headings";
import type { PublicAuthor } from "@/lib/api/public";
import { cn } from "@/lib/utils";

/**
 * Typography for a rendered article. Written out rather than pulled from a
 * plugin -- the web app carries no typography plugin -- and kept separate
 * from the console editor's own copy of this: that one styles an editable
 * TipTap surface, this one styles read-only output, and the two have no
 * reason to change together.
 *
 * `scroll-mt` on the headings is what makes a contents-list jump land below
 * the sticky header rather than underneath it.
 */
const articleStyles = cn(
  "text-[15px] leading-relaxed text-ink-800",
  "[&_h1]:mb-2.5 [&_h1]:mt-8 [&_h1]:text-[22px] [&_h1]:font-semibold [&_h1]:tracking-tight [&_h1]:text-ink-900",
  "[&_h2]:mb-2 [&_h2]:mt-7 [&_h2]:scroll-mt-24 [&_h2]:text-[18px] [&_h2]:font-semibold [&_h2]:tracking-tight [&_h2]:text-ink-900",
  "[&_h3]:mb-1.5 [&_h3]:mt-5 [&_h3]:scroll-mt-24 [&_h3]:text-[16px] [&_h3]:font-semibold [&_h3]:text-ink-900",
  "[&_p]:my-3",
  "[&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5",
  "[&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5",
  "[&_li]:my-1 [&_li>p]:my-0",
  "[&_blockquote]:my-4 [&_blockquote]:border-l-2 [&_blockquote]:border-accent-500 [&_blockquote]:pl-3 [&_blockquote]:text-ink-600",
  "[&_pre]:my-4 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-ink-900 [&_pre]:p-3 [&_pre]:font-mono [&_pre]:text-[13px] [&_pre]:text-ink-50",
  "[&_:not(pre)>code]:rounded [&_:not(pre)>code]:bg-ink-100 [&_:not(pre)>code]:px-1 [&_:not(pre)>code]:py-0.5 [&_:not(pre)>code]:font-mono [&_:not(pre)>code]:text-[13px]",
  "[&_a]:text-accent-950 [&_a]:underline [&_a]:underline-offset-2",
  "[&_hr]:my-6 [&_hr]:border-ink-200",
  "[&_img]:my-4 [&_img]:max-w-full [&_img]:rounded-md [&_img]:border [&_img]:border-ink-200",
  "[&_table]:my-4 [&_table]:w-full [&_table]:table-fixed [&_table]:border-collapse",
  "[&_td]:border [&_td]:border-ink-200 [&_td]:px-2 [&_td]:py-1.5 [&_td]:align-top",
  "[&_th]:border [&_th]:border-ink-200 [&_th]:bg-ink-50 [&_th]:px-2 [&_th]:py-1.5 [&_th]:text-left [&_th]:font-semibold",
);

/**
 * Rendered on the server -- in the portal and in the console preview alike
 * -- so there is no client clock to disagree with, and no hydration to
 * mismatch. UTC is pinned for the same reason: the date on an article is a
 * property of the article, not of whichever machine rendered it.
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

/**
 * One article, exactly as a reader sees it: title, subtitle, byline, body,
 * and a contents list beside it.
 *
 * Shared by `/help/[...path]` and the console's preview route rather than
 * copied into each. That is the whole point of the preview: a second
 * implementation would drift, and a member would then be previewing
 * something the help site does not render.
 *
 * There is deliberately no "was this helpful?" control here -- that is a
 * second anonymous write surface with no backend behind it, and it is being
 * designed separately.
 */
export function ArticleView({
  title,
  excerpt,
  doc,
  imageSrc,
  updatedAt,
  publishedAt,
  author,
}: {
  title: string;
  /** The subtitle under the title. Omitted entirely when empty. */
  excerpt: string;
  /** ProseMirror JSON. Walked defensively by `DocRenderer`; never trusted here. */
  doc: unknown;
  /** How this surface turns an image id into a URL its reader can actually fetch. */
  imageSrc: (id: string) => string;
  /** ISO-8601, from the API. */
  updatedAt: string;
  /** ISO-8601. Null on an article the console is previewing before publishing. */
  publishedAt: string | null;
  /** Null where the author's account has been deleted. */
  author: PublicAuthor | null;
}) {
  // One pass for both the anchors in the contents list and the ids on the
  // headings themselves, so the two cannot disagree.
  const headings = articleHeadings(doc);

  const published = formatted(publishedAt) ?? formatted(updatedAt);
  const updated = formatted(updatedAt);
  // Only when it says something the byline did not. An article published
  // and last touched on the same day would otherwise print that day twice
  // under two different labels.
  const showUpdated = updated !== null && updated !== published;

  return (
    <div className="flex flex-col gap-10 lg:flex-row lg:gap-12">
      <article className="min-w-0 flex-1">
        <h1 className="text-[30px] font-semibold leading-tight tracking-tight text-ink-900">
          {title}
        </h1>
        {excerpt && (
          <p
            data-testid="article-excerpt"
            className="mt-3 text-[15px] leading-relaxed text-ink-500"
          >
            {excerpt}
          </p>
        )}

        {(author || published) && (
          <div className="mt-5 flex items-center gap-2.5">
            {author && (
              <span
                aria-hidden
                className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-600 text-[11px] font-semibold text-white"
              >
                {author.monogram}
              </span>
            )}
            <span className="text-[13px] leading-tight text-ink-500">
              {author && (
                <span className="block text-ink-700">Written by {author.name}</span>
              )}
              {published && (
                <time dateTime={publishedAt ?? updatedAt} className="block">
                  {published}
                </time>
              )}
            </span>
          </div>
        )}

        <div className={cn(articleStyles, "mt-8")}>
          <DocRenderer doc={doc} imageSrc={imageSrc} headingId={headings.idFor} />
        </div>

        {showUpdated && (
          <footer className="mt-10 text-[13px] text-ink-500">
            Last updated <time dateTime={updatedAt}>{updated}</time>
          </footer>
        )}
      </article>

      {/* Below lg the contents list moves above the body, where a reader
          scrolling on a phone meets it before the prose rather than after. */}
      <ArticleToc
        headings={headings.list}
        className="order-first shrink-0 lg:sticky lg:top-24 lg:order-last lg:h-fit lg:w-56"
      />
    </div>
  );
}

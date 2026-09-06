import { DocRenderer } from "@/components/knowledge-base/doc-renderer";
import { cn } from "@/lib/utils";

/**
 * Typography for a rendered article. Written out rather than pulled from a
 * plugin -- the web app carries no typography plugin -- and kept separate
 * from the console editor's own copy of this: that one styles an editable
 * TipTap surface, this one styles read-only output, and the two have no
 * reason to change together.
 */
const articleStyles = cn(
  "text-[15px] leading-relaxed text-ink-800",
  "[&_h1]:mb-2.5 [&_h1]:mt-8 [&_h1]:text-[22px] [&_h1]:font-semibold [&_h1]:tracking-tight [&_h1]:text-ink-900",
  "[&_h2]:mb-2 [&_h2]:mt-7 [&_h2]:text-[18px] [&_h2]:font-semibold [&_h2]:tracking-tight [&_h2]:text-ink-900",
  "[&_h3]:mb-1.5 [&_h3]:mt-5 [&_h3]:text-[16px] [&_h3]:font-semibold [&_h3]:text-ink-900",
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
 * mismatch. UTC is pinned for the same reason: the date under an article is
 * a property of the article, not of whichever machine rendered it.
 */
const UPDATED_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

/**
 * One article, exactly as a reader sees it: title, a rule, the body, and
 * when it was last updated.
 *
 * Shared by `/help/{category}/{article}` and the console's preview route
 * rather than copied into each. That is the whole point of the preview: a
 * second implementation would drift, and a member would then be previewing
 * something the help site does not render.
 *
 * The footer holds the date and nothing else. There is deliberately no
 * "was this helpful?" control here -- that is a second anonymous write
 * surface with no backend behind it, and it is being designed separately.
 */
export function ArticleView({
  title,
  doc,
  imageSrc,
  updatedAt,
}: {
  title: string;
  /** ProseMirror JSON. Walked defensively by `DocRenderer`; never trusted here. */
  doc: unknown;
  /** How this surface turns an image id into a URL its reader can actually fetch. */
  imageSrc: (id: string) => string;
  /** ISO-8601, from the API. */
  updatedAt: string;
}) {
  const updated = new Date(updatedAt);
  const updatedLabel = Number.isNaN(updated.getTime())
    ? null
    : UPDATED_FORMAT.format(updated);

  return (
    <article>
      <h1 className="text-[30px] font-semibold leading-tight tracking-tight text-ink-900">
        {title}
      </h1>
      <hr className="mt-5 border-ink-200" />
      <div className={cn(articleStyles, "mt-6")}>
        <DocRenderer doc={doc} imageSrc={imageSrc} />
      </div>
      {updatedLabel && (
        <footer className="mt-10 text-[13px] text-ink-500">
          Last updated <time dateTime={updatedAt}>{updatedLabel}</time>
        </footer>
      )}
    </article>
  );
}

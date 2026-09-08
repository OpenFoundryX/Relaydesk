import type { ArticleHeading } from "@/components/portal/headings";
import { cn } from "@/lib/utils";

/**
 * The contents list beside an article.
 *
 * Its anchors and the ids on the headings themselves come from one pass
 * over the document (`articleHeadings`), so a row here cannot point at an
 * id the body never rendered.
 *
 * Renders nothing at all for an article with no headings -- a contents list
 * with one row, or none, is furniture rather than navigation.
 */
export function ArticleToc({
  headings,
  className,
}: {
  headings: ArticleHeading[];
  className?: string;
}) {
  if (headings.length < 2) return null;

  return (
    <nav
      aria-label="On this page"
      className={cn("border-l border-ink-200 pl-4", className)}
    >
      <ul className="space-y-3">
        {headings.map((heading) => (
          <li key={heading.id}>
            <a
              href={`#${heading.id}`}
              className={cn(
                "block text-[13px] leading-snug text-ink-500 hover:text-ink-900",
                heading.level === 3 && "pl-3",
              )}
            >
              {heading.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

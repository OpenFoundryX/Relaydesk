import { Artifact } from "@/components/marketing/artifacts";
import { cn } from "@/lib/utils";

/**
 * The embedded widget, as a floating product artifact.
 *
 * Shows the grounded path and the handoff in one frame, because that pair is
 * the product's actual claim: the answer carries numbered citations back to
 * real articles, and the thing it could not answer becomes a ticket instead of
 * a guess. Plain markup, so the page stays a server component and ships no JS.
 */
export function WidgetPreview({
  className,
  style,
}: {
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <Artifact
      style={style}
      className={cn("overflow-hidden", className)}
      // role/aria live on the inner wrapper so the shadow container stays a
      // plain box for assistive tech.
    >
      <div
        role="img"
        aria-label="The Relaydesk widget answering a question from a published help article, with numbered citations back to those articles"
      >
        <div className="px-5 pb-4 pt-5">
          <p className="text-[14px] text-ash-gray">Chronon Support</p>

          <p className="mt-4 text-[15px] leading-[1.5] text-slate-gray">
            Do you charge per seat? We&rsquo;re adding two more people this
            week.
          </p>

          <p className="mt-4 border-t border-hairline pt-4 text-[15px] leading-[1.5] text-ink-black">
            No. Relaydesk bills on resolved tickets, not on seats, so adding
            teammates costs nothing.
            <Cite n={1} /> Everyone in the workspace gets a login on every plan.
            <Cite n={2} />
          </p>

          <ul className="mt-4">
            <Source n={1} title="Pricing and billing" path="/help/billing/pricing" />
            <Source n={2} title="Inviting your team" path="/help/workspace/team" />
          </ul>
        </div>

        {/* Composer, in Steep's input geometry. */}
        <div className="px-3 pb-3">
          <div className="flex items-center gap-3 rounded-input border border-hairline px-4 py-3">
            <span className="text-[16px] text-smoke-gray">
              Ask anything…
              <span
                className="ml-0.5 inline-block h-[1.1em] w-px translate-y-[0.18em] animate-caret bg-ink-black"
                aria-hidden
              />
            </span>
            <span
              className="ml-auto flex size-10 shrink-0 items-center justify-center rounded-full bg-ink-black"
              aria-hidden
            >
              <svg viewBox="0 0 16 16" fill="none" className="size-4">
                <path
                  d="M3 8h10M9 4l4 4-4 4"
                  stroke="#ffffff"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
          </div>
        </div>

        <p className="border-t border-hairline px-5 py-4 text-[14px] leading-[1.5] text-slate-gray">
          <span className="text-ink-black">No article covers it?</span> It says
          so, and opens a ticket with the transcript already attached.
        </p>
      </div>
    </Artifact>
  );
}

/** The inline marker, matching the number the server issued to that article. */
function Cite({ n }: { n: number }) {
  return (
    <sup className="ml-0.5 text-[11px] font-w480 text-slate-gray">[{n}]</sup>
  );
}

function Source({ n, title, path }: { n: number; title: string; path: string }) {
  return (
    <li className="flex items-baseline gap-2.5 border-t border-hairline py-2.5">
      <span className="text-[13px] text-ash-gray">[{n}]</span>
      <span className="truncate text-[14px] font-w450 text-ink-black">
        {title}
      </span>
      <span className="truncate font-mono text-[12.5px] text-smoke-gray">
        {path}
      </span>
    </li>
  );
}

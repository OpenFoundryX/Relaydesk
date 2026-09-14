import { Artifact } from "@/components/marketing/artifacts";
import { cn } from "@/lib/utils";

/**
 * The scroll-linked product sequence.
 *
 * Four frames of the widget stacked on top of each other, cross-faded by the
 * page's scroll position rather than by a timer. This is deliberately NOT a
 * GIF or a video: a GIF runs on its own clock and would drift out of step
 * with the reader, and a video of a UI is heavier and blurrier than the UI
 * itself. The frames are real DOM, so they stay sharp, inherit the palette,
 * and cost nothing to download.
 *
 * The motion lives entirely in `globals.css` on a named view-timeline, so
 * this stays a server component with no JavaScript. Frame 1 is in normal
 * flow and the rest are absolutely positioned over it, which means a browser
 * without scroll-driven animation support -- or a reader who asked for
 * reduced motion -- sees frame 1 as a complete, static artifact rather than
 * a blank box or four overlapping ones.
 */
const steps = [
  {
    n: "01",
    tint: "bg-blush-peach",
    ink: "text-sienna-brown",
    title: "Someone asks",
    body: "A visitor types into the widget, or emails support@, or posts in your Discord. All three arrive the same way.",
  },
  {
    n: "02",
    tint: "bg-mist-blue",
    ink: "text-navy-ink",
    title: "Retrieval runs first",
    body: "Before the model sees anything, Relaydesk searches your published articles and numbers what came back. This is the step that decides whether there is an answer at all.",
  },
  {
    n: "03",
    tint: "bg-sage-green",
    ink: "text-forest-ink",
    title: "The answer cites its sources",
    body: "The model writes the reply and the markers. The server maps those markers back to the articles it actually retrieved, so an invented reference resolves to nothing.",
  },
  {
    n: "04",
    tint: "bg-lilac-haze",
    ink: "text-plum-ink",
    title: "Or it admits it cannot",
    body: "Nothing matched, so it does not guess. The conversation becomes a ticket with the whole transcript attached, and you pick it up knowing what was already asked.",
  },
];

export function AnswerSequence() {
  return (
    <div className="answer-seq lg:grid lg:grid-cols-2 lg:gap-10 xl:gap-14">
      <ol>
        {steps.map((step, index) => (
          <li
            key={step.n}
            className={cn(
              // The tall block is the scroll runway, and its height is load
              // bearing: it is what gives each of the four frames enough
              // scroll distance to be read. Shortening it to tighten the
              // page makes frames flash past. Tighten section padding
              // instead -- that is a separate knob. The copy centres inside
              // the block so no empty paper is stranded underneath.
              "seq-step py-4 lg:flex lg:min-h-[48vh] lg:flex-col lg:justify-center lg:py-0",
              `seq-step-${index + 1}`,
            )}
          >
            <div
              className={cn(
                "flex flex-col justify-center rounded-card p-9 lg:min-h-[270px]",
                step.tint,
                step.ink,
              )}
            >
              <p className="font-mono text-[14px] opacity-60">{step.n}</p>
              <h3 className="mt-4 font-display text-[30px] font-normal leading-[1.15] lg:text-[34px]">
                {step.title}
              </h3>
              <p className="mt-5 max-w-lg text-body opacity-80">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="mt-10 lg:mt-0">
        <div className="lg:sticky lg:top-[24vh]">
          {/* Frame 1 sets the height; 2-4 stack over it. */}
          <div className="seq-stack relative">
            <FrameAsk className="seq-frame seq-frame-1" />
            <FrameRetrieve className="seq-frame seq-frame-2" />
            <FrameAnswer className="seq-frame seq-frame-3" />
            <FrameEscalate className="seq-frame seq-frame-4" />
          </div>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Frames                                                                     */
/* -------------------------------------------------------------------------- */

function Shell({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Artifact className={cn("overflow-hidden", className)}>
      <div className="px-7 pb-7 pt-6">
        <p className="text-[15px] text-ash-gray">Chronon Support</p>
        {children}
      </div>
    </Artifact>
  );
}

function Composer({ caret }: { caret?: boolean }) {
  return (
    <div className="mt-6 flex items-center gap-3 rounded-input border border-hairline px-5 py-4">
      <span className="text-[16px] text-smoke-gray">
        Ask anything…
        {caret && (
          <span
            className="ml-0.5 inline-block h-[1.1em] w-px translate-y-[0.18em] animate-caret bg-ink-black"
            aria-hidden
          />
        )}
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
  );
}

function FrameAsk({ className }: { className?: string }) {
  return (
    <Shell className={className}>
      <p className="mt-5 text-[17px] leading-[1.5] text-slate-gray">
        Do you charge per seat? We&rsquo;re adding two more people this week.
      </p>
      <Composer caret />
      <p className="mt-5 border-t border-hairline pt-5 text-[14px] text-smoke-gray">
        Arrived from the widget · 0.0s
      </p>
    </Shell>
  );
}

function FrameRetrieve({ className }: { className?: string }) {
  const matches = [
    { title: "Pricing and billing", score: 0.91 },
    { title: "Inviting your team", score: 0.78 },
    { title: "Plans and limits", score: 0.42 },
  ];
  return (
    <Shell className={className}>
      <p className="mt-5 text-[17px] leading-[1.5] text-slate-gray">
        Searching 14 published articles…
      </p>
      <ul className="mt-4">
        {matches.map((m, i) => (
          <li
            key={m.title}
            className="flex items-center gap-3 border-t border-hairline py-3"
          >
            <span className="w-6 text-[14px] text-ash-gray">[{i + 1}]</span>
            <span className="flex-1 truncate text-[15.5px] font-w450 text-ink-black">
              {m.title}
            </span>
            <span className="h-1 w-20 shrink-0 overflow-hidden rounded-full bg-mist-gray">
              <span
                className="block h-full rounded-full bg-sienna-brown"
                style={{ width: `${m.score * 100}%` }}
              />
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-5 border-t border-hairline pt-5 text-[14px] text-smoke-gray">
        Two above threshold · the model is handed these and nothing else
      </p>
    </Shell>
  );
}

function FrameAnswer({ className }: { className?: string }) {
  return (
    <Shell className={className}>
      <p className="mt-5 text-[17px] leading-[1.5] text-ink-black">
        No. Relaydesk bills on resolved tickets, not on seats, so adding
        teammates costs nothing.
        <sup className="ml-0.5 text-[11px] font-w480 text-slate-gray">
          [1]
        </sup>{" "}
        Everyone in the workspace gets a login on every plan.
        <sup className="ml-0.5 text-[11px] font-w480 text-slate-gray">[2]</sup>
      </p>
      <ul className="mt-4">
        {[
          { n: 1, title: "Pricing and billing", path: "/help/billing/pricing" },
          { n: 2, title: "Inviting your team", path: "/help/workspace/team" },
        ].map((s) => (
          <li
            key={s.n}
            className="flex items-baseline gap-2.5 border-t border-hairline py-3 text-[13px]"
          >
            <span className="text-[14px] text-ash-gray">[{s.n}]</span>
            <span className="truncate text-[15.5px] font-w450 text-ink-black">
              {s.title}
            </span>
            <span className="truncate font-mono text-[12.5px] text-smoke-gray">
              {s.path}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-5 border-t border-hairline pt-5 text-[14px] text-smoke-gray">
        Recorded as <span className="font-mono">answered</span> · 1.8s
      </p>
    </Shell>
  );
}

function FrameEscalate({ className }: { className?: string }) {
  return (
    <Shell className={className}>
      <p className="mt-5 text-[17px] leading-[1.5] text-ink-black">
        I don&rsquo;t have an article covering that one. I&rsquo;ve passed it to
        the team with everything you&rsquo;ve told me.
      </p>
      <div className="mt-5 rounded-input bg-mist-gray px-5 py-4">
        <p className="text-[14px] text-ash-gray">Ticket #4812 · opened</p>
        <p className="mt-1.5 text-[15.5px] font-w450 text-ink-black">
          SAML login loops on the callback
        </p>
        <p className="mt-1.5 text-[14px] text-slate-gray">
          Transcript attached · 4 messages · priority set to High
        </p>
      </div>
      <p className="mt-5 border-t border-hairline pt-5 text-[14px] text-smoke-gray">
        Recorded as <span className="font-mono">escalated</span> · no guess made
      </p>
    </Shell>
  );
}

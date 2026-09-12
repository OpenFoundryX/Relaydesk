"use client";

/**
 * The Home tab's landing screen, modelled on Intercom's Messenger: a dark
 * band up top naming the workspace and greeting the visitor, then a couple
 * of cards on a light surface underneath offering the two ways in.
 *
 * Never shown at all when the knowledge base is empty -- see the `empty`
 * guard in panel.tsx, which opens straight into Compose instead and never
 * mounts this screen, so the "no search affordance" rule (spec D7) holds
 * without this component having to know about it.
 */
export function Home({
  workspaceName,
  name,
  aiEnabled,
  articleCount,
  onAsk,
  onCompose,
  onSearchHelp,
}: {
  workspaceName: string;
  /**
   * The visitor's own name, from the loader's `data-name` attribute (spec
   * §6) -- the same prefill Compose reads. Absent for the ordinary,
   * anonymous visitor: the greeting then drops the "Hello" line entirely
   * rather than printing "Hello ." or guessing at a name nobody gave.
   */
  name?: string;
  /** Whether this workspace can actually answer a question -- see panel.tsx. */
  aiEnabled?: boolean;
  articleCount: number;
  /** Opens the AI conversation. Only ever wired when `aiEnabled`. */
  onAsk: () => void;
  /** Opens the message form -- what the primary card does instead of
   *  `onAsk` when there is no AI to ask. */
  onCompose: () => void;
  /** Switches the panel to the Help tab. */
  onSearchHelp: () => void;
}) {
  return (
    <div className="flex flex-1 flex-col">
      {/* The dark band. Its own surface, deliberately not following
          `prefers-color-scheme` the way the rest of the panel does -- it
          reads as one continuous piece with Header just above it, which is
          dark unconditionally for the same reason (spec D5). */}
      <div className="shrink-0 bg-ink-950 px-4 py-6">
        <p className="text-[12px] font-medium text-white/60">{workspaceName}</p>
        {name && name.trim() !== "" ? (
          <>
            <p className="mt-3 text-[14px] text-white/70">Hello {name}.</p>
            <p className="text-[20px] font-semibold tracking-tight text-white">
              How can we help?
            </p>
          </>
        ) : (
          <p className="mt-3 text-[20px] font-semibold tracking-tight text-white">
            How can we help?
          </p>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-2 bg-ink-50 px-4 py-4 dark:bg-ink-950">
        <button
          type="button"
          onClick={aiEnabled ? onAsk : onCompose}
          className="rounded-xl border border-ink-200 bg-white px-3.5 py-2.5 text-left text-[13px] transition-colors hover:border-ink-300 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:border-ink-700 dark:bg-ink-800 dark:hover:border-ink-600"
        >
          <span className="block font-medium text-ink-900 dark:text-white">
            {aiEnabled ? "Ask a question" : "Send us a message"}
          </span>
          <span className="block text-[12px] text-ink-500 dark:text-ink-400">
            {aiEnabled
              ? "Our AI answers from your help articles"
              : "We'll reply by email as soon as we can."}
          </span>
        </button>

        {/* Slice 8's rule, kept exactly: no article at all means no search
            affordance anywhere in the panel -- a search box (or, here, a
            card that leads to one) over nothing makes the product look
            broken on the day it is being judged. */}
        {articleCount > 0 && (
          <button
            type="button"
            onClick={onSearchHelp}
            className="rounded-xl border border-ink-200 bg-white px-3.5 py-2.5 text-left text-[13px] transition-colors hover:border-ink-300 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:border-ink-700 dark:bg-ink-800 dark:hover:border-ink-600"
          >
            <span className="block font-medium text-ink-900 dark:text-white">
              {/* Not "Search for help": that is the Help tab's own search
                  field, and two controls with the same name in one panel
                  is ambiguous to a screen reader and to a test. This card
                  opens the shelf; the field inside it searches. */}
              Browse help articles
            </span>
            <span className="block text-[12px] text-ink-500 dark:text-ink-400">
              Browse {articleCount} {articleCount === 1 ? "article" : "articles"}
            </span>
          </button>
        )}
      </div>
    </div>
  );
}

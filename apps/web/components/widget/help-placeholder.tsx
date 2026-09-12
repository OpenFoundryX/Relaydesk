/**
 * Stand-in for the Help tab while it is being built (concurrently, in
 * `help.tsx`) by another agent. That file replaces this one wholesale --
 * search, results and reading an article all move under it -- so nothing
 * here should grow real behaviour; anything worth keeping belongs there
 * instead.
 *
 * The contract the real component should honour, once it lands:
 *  - It receives `articleCount` and `widgetKey` the same way this stub does.
 *  - Reading an article is a full-height screen with its own back control,
 *    exactly like Article was under the old flat view -- when the visitor
 *    is in one, call `onFullScreenChange(true)` so `panel.tsx` hides the tab
 *    bar, and `onFullScreenChange(false)` on the way back out (see
 *    `panel.tsx`'s `helpFullScreen` state).
 *  - `onCompose` opens the message form on the Home tab, exactly as it does
 *    from Ask's escalation offer -- pass it straight through to whatever
 *    plays the part Results and Article used to (their "Send a message"
 *    button).
 *  - The `Search for an answer` input placeholder and the `role="search"`
 *    form it lived in (see the plan at
 *    `docs/superpowers/plans/2026-09-10-support-widget.md`) are a stable
 *    contract other tests were written against -- keep that exact string
 *    wherever the search box ends up.
 */
export function HelpTabPlaceholder({ articleCount }: { articleCount: number }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-1 px-6 py-10 text-center">
      <p className="text-[13px] text-ink-500 dark:text-ink-400">
        {articleCount > 0
          ? "Help articles are on their way."
          : "There's nothing to search here yet."}
      </p>
    </div>
  );
}

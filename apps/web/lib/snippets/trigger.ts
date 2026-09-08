/**
 * Where the `/` menu is, in a plain textarea.
 *
 * Kept apart from the composer so the rules below are decided by tests
 * rather than by clicking around: which slash counts, what an agent has
 * typed after it, and what the reply reads like once a snippet is chosen.
 */

export interface SnippetTrigger {
  /** What the agent has typed after the slash, used to filter titles. */
  query: string;
  /** Index of the slash. */
  start: number;
  /** Index just past the query — the caret, when the trigger is live. */
  end: number;
}

/** Longest query the menu will follow, after which it gives up. */
const MAX_QUERY = 32;

/**
 * The live snippet trigger at `caret`, or null when there is none.
 *
 * A slash only counts at the start of the reply or straight after
 * whitespace, which is what keeps the menu shut inside a URL — by far the
 * most common way a slash lands in a support reply. The query runs to the
 * caret and cannot contain whitespace, so typing a space dismisses the menu
 * and leaves the slash as ordinary text.
 */
export function snippetTrigger(value: string, caret: number): SnippetTrigger | null {
  const before = value.slice(0, caret);
  const start = before.lastIndexOf("/");
  if (start === -1) return null;

  const preceding = start === 0 ? "" : before[start - 1];
  if (preceding !== "" && !/\s/.test(preceding)) return null;

  const query = before.slice(start + 1);
  if (query.length > MAX_QUERY || /\s/.test(query)) return null;

  return { query, start, end: caret };
}

/** The reply, and where the caret lands, once `text` replaces the trigger. */
export function applySnippet(
  value: string,
  trigger: SnippetTrigger,
  text: string,
): { value: string; caret: number } {
  return {
    value: value.slice(0, trigger.start) + text + value.slice(trigger.end),
    caret: trigger.start + text.length,
  };
}

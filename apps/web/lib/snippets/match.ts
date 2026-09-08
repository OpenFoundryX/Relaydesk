import type { Snippet } from "@/lib/types";

/**
 * The snippets the `/` menu offers for `query`, best match first.
 *
 * Substring rather than prefix-only: titles are phrases ("Issue resolved",
 * "Request more info") and the word an agent reaches for is often not the
 * first one. A title that does start with the query still wins, so the
 * obvious guess stays at the top where Enter will take it.
 *
 * The API already returns snippets in title order, and that order is kept
 * within each of the two groups.
 */
export function matchSnippets(snippets: Snippet[], query: string): Snippet[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return snippets;

  const starts: Snippet[] = [];
  const contains: Snippet[] = [];
  for (const snippet of snippets) {
    const title = snippet.title.toLowerCase();
    if (title.startsWith(needle)) starts.push(snippet);
    else if (title.includes(needle)) contains.push(snippet);
  }
  return [...starts, ...contains];
}

/**
 * Instant article search, scored in the browser.
 *
 * The help centre's searchable surface is bounded (hundreds of articles at
 * most), fixed for the length of a visit, and small once bodies are left
 * out -- so the whole index is fetched once and every keystroke after that
 * is an in-memory scan. At this size no network call can compete: the
 * round trip alone costs more than scoring the entire index.
 *
 * What it deliberately cannot do is find a phrase that appears only in an
 * article's body. Bodies are what make a knowledge base too large to ship,
 * so they stay on the server, and pressing Enter falls through to
 * `/help/search`, which is Postgres full-text over exactly that.
 *
 * Visibility is resolved before any of this: the endpoint feeding it emits
 * published, external articles only, so nothing here has to know what a
 * draft is.
 */

/** One row of the index, as the API sends it. */
export interface SearchEntry {
  id: string;
  title: string;
  excerpt: string;
  /** Slash-joined help-site path, no leading slash. */
  path: string;
  /** The collections above it, root first. */
  collections: string[];
}

export interface SearchResult extends SearchEntry {
  score: number;
}

/** An entry with its fields pre-tokenised, so scoring touches no strings. */
interface IndexedEntry {
  entry: SearchEntry;
  title: string;
  titleTokens: string[];
  collectionTokens: string[];
  excerptTokens: string[];
}

export type SearchIndex = IndexedEntry[];

/**
 * Field weights. A word in the title says far more about what an article is
 * than the same word buried in its blurb, and the collection sits between
 * the two -- people describe an article by where it lives.
 */
const WEIGHT = { title: 10, collection: 4, excerpt: 2 } as const;

/** A word the reader has not finished typing counts, but for less. */
const PREFIX_FACTOR = 0.6;

/** The query as one string, found verbatim. Worth more than its parts. */
const PHRASE_BONUS = { title: 25, excerpt: 8 } as const;

function normalise(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function tokenise(text: string): string[] {
  const normalised = normalise(text);
  return normalised ? normalised.split(" ") : [];
}

/**
 * Prepare the index once, when it arrives.
 *
 * Tokenising here rather than per keystroke is most of why this stays fast:
 * a query then costs one pass of string comparisons over already-split
 * words, with no parsing in the hot path.
 */
export function buildSearchIndex(entries: SearchEntry[]): SearchIndex {
  return entries.map((entry) => ({
    entry,
    title: normalise(entry.title),
    titleTokens: tokenise(entry.title),
    collectionTokens: entry.collections.flatMap(tokenise),
    excerptTokens: tokenise(entry.excerpt),
  }));
}

/** Full weight for an exact word, less for one still being typed. */
function tokenScore(term: string, tokens: string[], weight: number): number {
  let best = 0;
  for (const token of tokens) {
    if (token === term) return weight;
    if (token.startsWith(term)) best = Math.max(best, weight * PREFIX_FACTOR);
  }
  return best;
}

/**
 * How much of the query an article actually answers, as a multiplier.
 *
 * Without this, scoring each term separately and adding the points lets a
 * word that appears all over the index drag the wrong article to the top:
 * for "mileage expense", an article called "Creating expenses" collects
 * most of the points that "Create a mileage expense" does, because
 * "expense" is worth the same to both. Weighting by the *fraction* of the
 * query matched separates them by a wide margin instead of a hair, and it
 * does so without hand-tuning any of the individual weights above.
 */
function coverage(matched: number, total: number): number {
  if (total === 0) return 0;
  const fraction = matched / total;
  if (fraction === 1) return 2 + 0.3 * total;
  if (fraction >= 0.75) return 1.5;
  if (fraction >= 0.5) return 1;
  return 0.4;
}

export function searchArticles(
  index: SearchIndex,
  query: string,
  limit = 8,
): SearchResult[] {
  const terms = tokenise(query);
  if (terms.length === 0) return [];
  const phrase = normalise(query);

  const results: SearchResult[] = [];

  for (const doc of index) {
    let base = 0;
    let matched = 0;

    for (const term of terms) {
      const score = Math.max(
        tokenScore(term, doc.titleTokens, WEIGHT.title),
        tokenScore(term, doc.collectionTokens, WEIGHT.collection),
        tokenScore(term, doc.excerptTokens, WEIGHT.excerpt),
      );
      if (score > 0) {
        base += score;
        matched += 1;
      }
    }

    if (matched === 0) continue;

    // The whole query, found as written. A title that contains the phrase
    // outright is almost always the article somebody meant.
    if (terms.length > 1) {
      if (doc.title.includes(phrase)) base += PHRASE_BONUS.title;
      else if (normalise(doc.entry.excerpt).includes(phrase)) {
        base += PHRASE_BONUS.excerpt;
      }
    }

    results.push({ ...doc.entry, score: base * coverage(matched, terms.length) });
  }

  return results
    .sort((a, b) =>
      b.score === a.score ? a.title.length - b.title.length : b.score - a.score,
    )
    .slice(0, limit);
}

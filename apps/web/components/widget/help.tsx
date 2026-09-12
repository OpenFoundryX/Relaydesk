"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, ChevronRight, Search } from "lucide-react";

import { Article } from "@/components/widget/article";
import { Results } from "@/components/widget/results";
import { WidgetButton } from "@/components/widget/button";

/**
 * A collection as `/widget/kb/collections` lists it -- mirrors
 * `PublicCollectionOut` (relaydesk.schemas.kb): name, slug, a blurb that
 * may be empty, an icon this v1 doesn't draw, and `articleCount` for the
 * whole subtree (a collection whose articles all live in sections would
 * otherwise read as empty). Kept here rather than in `lib/api/widget.ts`:
 * this tab is that route's only caller.
 */
export interface HelpCollection {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string;
  articleCount: number;
}

/** Where the article view returns to when its back control is used. */
type Back = { name: "browse" } | { name: "collection"; collection: HelpCollection };

type View =
  | { name: "browse" }
  | { name: "collection"; collection: HelpCollection }
  | { name: "article"; path: string; back: Back };

/**
 * The panel's Help tab: search, a browsable list of article collections,
 * a collection's articles, and the article itself -- the same shape as
 * Intercom's Messenger Help pane.
 *
 * Self-contained by design: it takes only `widgetKey` and `onCompose`
 * (whatever shell mounts it, tabbed or otherwise, needs to know nothing
 * about search, collections or articles as separate screens) and owns
 * every transition between its four views itself, the way `panel.tsx`
 * used to own transitions between Home, Results and Article.
 *
 * Reuses `Results` and `Article` rather than re-implementing a search
 * list or an article renderer -- both already do exactly this job, doc
 * rendering included, and a second copy of either would only drift from
 * the first.
 */
export function Help({
  widgetKey,
  onCompose,
}: {
  widgetKey: string | undefined;
  onCompose: () => void;
}) {
  const [typed, setTyped] = useState("");
  // Committed only on submit, same as Home/Results (spec D8: search runs
  // on submit, not per keystroke) -- typing alone never fires a request.
  const [query, setQuery] = useState("");
  const [view, setView] = useState<View>({ name: "browse" });

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQuery(typed.trim());
  }

  function onTypedChange(value: string) {
    setTyped(value);
    // Clearing the field by hand has nothing to submit, so it drops
    // straight back to the collections list rather than waiting for an
    // Enter that would only search for "" and show "nothing matched".
    if (value.trim() === "") setQuery("");
  }

  return (
    <div className="flex flex-1 flex-col">
      {view.name === "browse" && (
        <div className="px-4 pt-6">
          <form role="search" onSubmit={submitSearch} className="relative">
            <label htmlFor="help-search" className="sr-only">
              Search for help
            </label>
            <Search
              aria-hidden
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400"
            />
            <input
              id="help-search"
              type="search"
              value={typed}
              onChange={(event) => onTypedChange(event.target.value)}
              placeholder="Search for help"
              className="h-9 w-full rounded-md border border-ink-200 bg-white pl-9 pr-3 text-[13px] text-ink-900 placeholder:text-ink-400 transition-colors hover:border-ink-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:border-ink-700 dark:bg-ink-800 dark:text-white dark:placeholder:text-ink-400"
            />
          </form>
        </div>
      )}

      {view.name === "browse" && query === "" && (
        <Collections
          widgetKey={widgetKey}
          onOpen={(collection) => setView({ name: "collection", collection })}
          onCompose={onCompose}
        />
      )}

      {view.name === "browse" && query !== "" && (
        <Results
          key={query}
          widgetKey={widgetKey}
          query={query}
          onOpen={(path) => setView({ name: "article", path, back: { name: "browse" } })}
          onCompose={onCompose}
        />
      )}

      {view.name === "collection" && (
        <CollectionArticles
          key={view.collection.slug}
          widgetKey={widgetKey}
          collection={view.collection}
          onBack={() => setView({ name: "browse" })}
          onOpen={(path) =>
            setView({ name: "article", path, back: { name: "collection", collection: view.collection } })
          }
          onCompose={onCompose}
        />
      )}

      {view.name === "article" && (
        <div className="flex flex-1 flex-col">
          <div className="px-4 pt-6">
            <BackButton onClick={() => setView(view.back)} />
          </div>
          <Article key={view.path} widgetKey={widgetKey} path={view.path} onCompose={onCompose} />
        </div>
      )}
    </div>
  );
}

/** The one back control every sub-screen here uses, lifted verbatim from
 * `compose.tsx`'s own back button so it reads identically wherever it
 * shows up in the panel. */
function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="-mt-1 flex w-fit items-center gap-1.5 text-[12px] text-ink-500 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:text-ink-400 dark:hover:text-white"
    >
      <ArrowLeft className="size-3.5" aria-hidden />
      Back
    </button>
  );
}

/**
 * The Help tab's front page: every root collection, its blurb, its
 * article count, and a chevron to open it. Shown whenever nothing is
 * being searched. "Send a message" is secondary here, same reasoning as
 * Home -- browsing collections is not yet a failed attempt to self-serve.
 */
function Collections({
  widgetKey,
  onOpen,
  onCompose,
}: {
  widgetKey: string | undefined;
  onOpen: (collection: HelpCollection) => void;
  onCompose: () => void;
}) {
  const [collections, setCollections] = useState<HelpCollection[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    const request = widgetKey
      ? fetch(`/widget/kb/collections?key=${encodeURIComponent(widgetKey)}`).then((response) =>
          response.ok ? response.json() : [],
        )
      : Promise.resolve([]);
    request
      .then((found: HelpCollection[]) => {
        if (!cancelled) setCollections(found);
      })
      .catch(() => {
        if (!cancelled) setCollections([]);
      });
    return () => {
      cancelled = true;
    };
  }, [widgetKey]);

  const loading = collections === null;

  return (
    <div className="flex flex-1 flex-col gap-4 px-4 py-6">
      {loading ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : collections.length === 0 ? (
        <p className="text-[13px] text-ink-500 dark:text-ink-400">
          There&apos;s nothing to browse yet. Send us a message instead.
        </p>
      ) : (
        <ul className="flex flex-col gap-1">
          {collections.map((collection) => (
            <li key={collection.id}>
              <button
                type="button"
                onClick={() => onOpen(collection)}
                className="flex w-full items-center gap-3 rounded-lg border border-ink-200 bg-white p-3 text-left transition-colors hover:border-ink-300 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:border-ink-700 dark:bg-ink-800 dark:hover:bg-ink-700"
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium text-ink-900 dark:text-white">
                    {collection.name}
                  </span>
                  {collection.description && (
                    <span className="mt-0.5 line-clamp-2 block text-[12px] text-ink-500 dark:text-ink-400">
                      {collection.description}
                    </span>
                  )}
                  <span className="mt-1 block text-[12px] text-ink-400">
                    {collection.articleCount} {collection.articleCount === 1 ? "article" : "articles"}
                  </span>
                </span>
                <ChevronRight aria-hidden className="size-4 shrink-0 text-ink-400" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-auto pt-2">
        <WidgetButton type="button" variant="secondary" onClick={onCompose}>
          Send a message
        </WidgetButton>
      </div>
    </div>
  );
}

/** One article row inside a collection -- no body, no doc, matches
 * `PublicArticleSummary`. Declared locally for the same reason
 * `HelpCollection` is: this tab is the only caller of the route that
 * returns it. */
interface HelpArticleSummary {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  path: string;
}

/**
 * One collection's articles: a back control, the collection's own name,
 * then its articles as rows. "Send a message" is primary here, same
 * reasoning as Results -- opening a specific collection is already an
 * attempt to self-serve.
 */
function CollectionArticles({
  widgetKey,
  collection,
  onBack,
  onOpen,
  onCompose,
}: {
  widgetKey: string | undefined;
  collection: HelpCollection;
  onBack: () => void;
  onOpen: (path: string) => void;
  onCompose: () => void;
}) {
  const [articles, setArticles] = useState<HelpArticleSummary[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    const request = widgetKey
      ? fetch(
          `/widget/kb/collections?key=${encodeURIComponent(widgetKey)}&path=${encodeURIComponent(collection.slug)}`,
        ).then((response) => (response.ok ? response.json() : null))
      : Promise.resolve(null);
    request
      .then((found: { articles: HelpArticleSummary[] } | null) => {
        if (!cancelled) setArticles(found ? found.articles : []);
      })
      .catch(() => {
        if (!cancelled) setArticles([]);
      });
    return () => {
      cancelled = true;
    };
  }, [widgetKey, collection.slug]);

  const loading = articles === null;

  return (
    <div className="flex flex-1 flex-col gap-4 px-4 py-6">
      <BackButton onClick={onBack} />

      <h1 className="text-[15px] font-semibold tracking-tight text-ink-900 dark:text-white">
        {collection.name}
      </h1>

      {loading ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : articles.length === 0 ? (
        <p className="text-[13px] text-ink-500 dark:text-ink-400">
          Nothing in here yet. Send us a message instead.
        </p>
      ) : (
        <ul className="flex flex-col gap-1">
          {articles.map((article) => (
            <li key={article.id}>
              <button
                type="button"
                onClick={() => onOpen(article.path)}
                className="block w-full rounded-lg border border-ink-200 bg-white p-3 text-left transition-colors hover:border-ink-300 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:border-ink-700 dark:bg-ink-800 dark:hover:bg-ink-700"
              >
                <span className="block text-[13px] font-medium text-ink-900 dark:text-white">
                  {article.title}
                </span>
                {article.excerpt && (
                  <span className="mt-0.5 line-clamp-2 block text-[12px] text-ink-500 dark:text-ink-400">
                    {article.excerpt}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-auto pt-2">
        <WidgetButton type="button" variant="primary" onClick={onCompose}>
          Send a message
        </WidgetButton>
      </div>
    </div>
  );
}

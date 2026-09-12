import { NextRequest, NextResponse } from "next/server";

import { ApiError, apiFetch } from "@/lib/api/client";

/**
 * The Help tab's own collections browsing, proxied server-side for the
 * same reason `kb/search/route.ts` is: the frame is a Client Component
 * with no path to the API directly (see that file's docstring).
 *
 * One route does both of the Help tab's two reads rather than two files,
 * distinguished by whether `path` is present:
 *
 *  - no `path`: the root collections list, `GET /widget/{key}/kb`
 *    (`PublicCollectionOut[]` -- id, name, slug, description, icon,
 *    articleCount; see `relaydesk.api.widget.kb_index`).
 *  - `path` set to a collection's own slug: that collection's articles,
 *    resolved through `GET /widget/{key}/kb/{path}`
 *    (`PublicCategoryNodeOut`) and flattened from its direct articles and
 *    every section's, since `article_count`'s own docstring notes a
 *    collection whose articles all live in its sections would otherwise
 *    read as empty -- the same subtlety applies to listing them.
 *
 * Not added to `lib/api/widget.ts`: this route is that shape's only
 * caller, same as `getWidgetArticle` is `kb/article/route.ts`'s.
 */

interface CollectionSummary {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string;
  articleCount: number;
}

interface ArticleSummary {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  path: string;
}

interface SectionOut {
  articles: ArticleSummary[];
}

// The two shapes `GET /widget/{key}/kb/{path}` answers with (see
// `PublicCategoryNodeOut` / `PublicArticleNodeOut`, `relaydesk.schemas.kb`).
// Only the category branch is used here -- Help only ever passes a
// collection's own slug, resolved from a list this route already served.
type Node =
  | { kind: "category"; category: CollectionSummary; sections: SectionOut[]; articles: ArticleSummary[] }
  | { kind: "article" };

export async function GET(request: NextRequest) {
  const key = request.nextUrl.searchParams.get("key");
  const path = request.nextUrl.searchParams.get("path");
  if (!key) return NextResponse.json(path ? null : []);

  try {
    if (!path) {
      const collections = await apiFetch<CollectionSummary[]>(
        `/widget/${encodeURIComponent(key)}/kb`,
        { auth: false },
      );
      return NextResponse.json(collections);
    }

    // Encoded per segment, not as one string -- see `getWidgetArticle` in
    // `lib/api/widget.ts` for why a slash-joined path needs this.
    const encoded = path.split("/").map(encodeURIComponent).join("/");
    const node = await apiFetch<Node>(`/widget/${encodeURIComponent(key)}/kb/${encoded}`, {
      auth: false,
    });
    if (node.kind !== "category") return NextResponse.json(null);

    const articles = [...node.articles, ...node.sections.flatMap((section) => section.articles)];
    return NextResponse.json({ collection: node.category, articles });
  } catch (error) {
    // An unknown or deactivated key, or a collection slug that no longer
    // exists, answers identically to "nothing here" -- the frame's session
    // can outlive either, same reasoning as `searchWidgetKb`'s own catch.
    if (error instanceof ApiError && error.status === 404) {
      return NextResponse.json(path ? null : []);
    }
    throw error;
  }
}

import type { PublicCategory } from "@/lib/api/public";

/** One row under a category. `href` is whatever the surface links articles to. */
export interface PortalTreeArticle {
  id: string;
  title: string;
  href: string;
}

export interface PortalTreeCategory {
  id: string;
  name: string;
  /**
   * The category's own page, or null where the surface has none -- the
   * console preview has no equivalent of `/help/{category}`, and a link
   * that goes nowhere is worse than a plain label.
   */
  href: string | null;
  articles: PortalTreeArticle[];
}

/**
 * The public help index, shaped for `PortalKbSidebar`.
 *
 * Its own module rather than a helper hanging off the sidebar: the sidebar
 * is a client component, and everything a `"use client"` module exports
 * becomes a client reference -- so a server page could not call this if it
 * lived there. The types travel with it for the same reason.
 *
 * Nothing is filtered here. The index the API returns is already only
 * published articles in external categories, and re-deciding that in the
 * browser bundle would be the visibility rule stated twice.
 */
export function helpTree(categories: PublicCategory[]): PortalTreeCategory[] {
  return categories.map((category) => ({
    id: category.id,
    name: category.name,
    href: `/help/${category.slug}`,
    articles: category.articles.map((article) => ({
      id: article.id,
      title: article.title,
      href: `/help/${category.slug}/${article.slug}`,
    })),
  }));
}

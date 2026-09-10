import { NextRequest, NextResponse } from "next/server";

import { getWidgetArticle } from "@/lib/api/widget";

/**
 * One article, for the panel's own Article screen. See
 * `widget/kb/search/route.ts` for why this is a route rather than a direct
 * client fetch.
 */
export async function GET(request: NextRequest) {
  const key = request.nextUrl.searchParams.get("key");
  const path = request.nextUrl.searchParams.get("path");
  if (!key || !path) return new NextResponse(null, { status: 404 });

  const article = await getWidgetArticle(key, path);
  if (!article) return new NextResponse(null, { status: 404 });
  return NextResponse.json(article);
}

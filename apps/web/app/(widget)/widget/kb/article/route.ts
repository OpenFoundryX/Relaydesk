import { NextRequest, NextResponse } from "next/server";

import { getWidgetArticle } from "@/lib/api/widget";

/**
 * One article, for the panel's own Article screen -- its `ancestors`
 * included, so that screen can find the collection to draw "Related
 * articles" from without a second door onto the tree. See
 * `widget/kb/search/route.ts` for why this is a route rather than a direct
 * client fetch.
 */
export async function GET(request: NextRequest) {
  const key = request.nextUrl.searchParams.get("key");
  const path = request.nextUrl.searchParams.get("path");
  if (!key || !path) return new NextResponse(null, { status: 404 });

  const page = await getWidgetArticle(key, path);
  if (!page) return new NextResponse(null, { status: 404 });
  return NextResponse.json(page);
}

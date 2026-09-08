"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { Suspense } from "react";

import { PortalNav } from "@/components/portal/portal-nav";
import { PortalSearch } from "@/components/portal/portal-search";

/**
 * The dark band at the top of every portal page: who this help centre
 * belongs to, the two portal surfaces, and the search box.
 *
 * The headline only appears on the help centre's front page. On an article
 * or a collection the reader has already arrived somewhere and the heading
 * they want is the page's own -- a second, larger one above it would push
 * the content down on every page to introduce it on one.
 *
 * A client component to read the path for that decision; the workspace's
 * own details are passed down from the server layout, which is where they
 * are fetched.
 */
export function PortalHero({
  name,
  monogram,
}: {
  name: string;
  monogram: string;
}) {
  const pathname = usePathname();
  const isFrontPage = pathname === "/help";

  return (
    <header className="relative bg-ink-950">
      {/* A soft wash of the brand colour behind the bar. Decorative, and
          deliberately not an image: it costs no request and cannot fail to
          load, leaving a black rectangle.

          The clipping lives on this wrapper rather than on the header, so
          that the glow stays inside the band while the search
          suggestions -- absolutely positioned inside the same header --
          can still hang below it. `overflow-hidden` on the header itself
          cut them off at the black edge. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div className="absolute -top-32 right-0 size-96 rounded-full bg-accent-600/20 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-5xl px-6">
        <div className="flex min-h-14 flex-wrap items-center gap-x-6 gap-y-2 py-3">
          <Link href="/help" className="flex items-center gap-2">
            <span className="flex size-6 items-center justify-center rounded-md bg-white text-[10px] font-semibold text-ink-900">
              {monogram}
            </span>
            <span className="text-[15px] font-semibold tracking-tight text-white">
              {name}
            </span>
          </Link>
          <PortalNav tone="dark" className="ml-auto" />
        </div>

        <div className={isFrontPage ? "pb-14 pt-6" : "pb-6"}>
          {isFrontPage && (
            <h1 className="mb-5 text-center text-[22px] font-semibold tracking-tight text-white">
              How can we help?
            </h1>
          )}
          {/*
           * Reads `?q=` to prefill itself, which is a dynamic read -- hence
           * the boundary, the way the console does it in
           * app/(console)/knowledge-base/layout.tsx.
           */}
          <Suspense fallback={<div className="h-12" />}>
            <PortalSearch tone="dark" className="mx-auto max-w-2xl" />
          </Suspense>
        </div>
      </div>
    </header>
  );
}

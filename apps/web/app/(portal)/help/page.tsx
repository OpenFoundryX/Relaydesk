import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { CollectionCard } from "@/components/portal/collection-card";
import { getPublicCollections } from "@/lib/api/public";

export const metadata: Metadata = { title: "Knowledge Base" };

/**
 * The help centre's front page: one card per root collection.
 *
 * Only the top level. The collections below it are reached by opening one,
 * which is what the cards are for -- listing every article in the workspace
 * here, as this page used to, meant the front page grew without bound and
 * said nothing about how the help centre is organised.
 *
 * A collection with nothing published anywhere beneath it never arrives:
 * the API omits it, so there is nothing empty to hide here.
 */
export default async function HelpIndexPage() {
  const slug = (await headers()).get("x-relaydesk-workspace");
  if (!slug) notFound();

  const collections = await getPublicCollections(slug);

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      {collections.length === 0 ? (
        <p className="text-[13px] text-ink-500">There are no help articles yet.</p>
      ) : (
        <div className="grid gap-3">
          {collections.map((collection) => (
            <CollectionCard
              key={collection.id}
              collection={collection}
              href={`/help/${collection.slug}`}
            />
          ))}
        </div>
      )}
    </main>
  );
}

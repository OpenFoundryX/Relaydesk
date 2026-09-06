import type { ArticleStatus } from "@/lib/types";

/**
 * The review workflow, mirroring `ALLOWED_TRANSITIONS` in the API's
 * `services/kb_articles.py`. The API is the authority: it refuses anything
 * outside its own table, so an entry added here that the API does not allow
 * would surface as a rejected transition rather than a new capability. Keep
 * the two in step.
 *
 * Note what is absent: there is no `published -> ready`. An article that is
 * live goes back to draft or stays live, and nothing in the console may
 * offer a third option.
 */
export const TRANSITIONS: Record<ArticleStatus, ReadonlyArray<ArticleStatus>> = {
  draft: ["ready"],
  ready: ["draft", "published"],
  published: ["draft"],
};

/**
 * A Publish button that cannot be pressed carries no destination at all --
 * naming one would put a target in the table that is not an edge out of the
 * current state, and "it is disabled anyway" is a weaker guarantee than not
 * having written it down.
 */
export type PublishButton = { enabled: false } | { enabled: true; to: ArticleStatus };

export interface StatusControl {
  /** The toggle's label, and its accessible name. */
  toggleLabel: string;
  toggleOn: boolean;
  /** Where flipping the toggle sends the article. */
  toggleTo: ArticleStatus;
  /** `null` hides the Publish button rather than disabling it. */
  publish: PublishButton | null;
}

/**
 * How the status control reads in each state -- a toggle, plus a Publish
 * button that is disabled until the article is ready and gone once it is
 * live.
 *
 * Every target named here is an edge in `TRANSITIONS` above, which is what
 * keeps the control from ever offering something the API would refuse; the
 * unit tests check that property rather than trusting this comment. On a
 * published article the toggle is the unpublish: it reads "Published", and
 * turning it off takes the article back to draft -- not to ready, which is
 * not an edge the API has.
 */
export const STATUS_CONTROL: Record<ArticleStatus, StatusControl> = {
  draft: {
    toggleLabel: "Ready to publish",
    toggleOn: false,
    toggleTo: "ready",
    publish: { enabled: false },
  },
  ready: {
    toggleLabel: "Ready to publish",
    toggleOn: true,
    toggleTo: "draft",
    publish: { enabled: true, to: "published" },
  },
  published: {
    toggleLabel: "Published",
    toggleOn: true,
    toggleTo: "draft",
    publish: null,
  },
};

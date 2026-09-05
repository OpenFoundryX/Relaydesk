# Knowledge Base — Design

**Sub-project 3 of the Relaydesk backend.** Builds on
`2026-09-04-tenancy-and-inbox-core-design.md` (slice 1) and
`2026-09-04-email-channel-design.md` (slice 2), which remain binding for
multi-tenancy, sessions, the conversation model, the worker tier, and the
content-addressed attachment store this slice reuses.

## 1. Goal

Give a workspace somewhere to write things down, for two audiences that need
the same content in different states of readiness.

**Internal** articles are the procedures an agent follows — and, from slice 4
onward, the grounding an AI agent retrieves against when drafting a reply.
**External** articles are the customer-facing knowledge hub, served on the
workspace's own portal subdomain to anyone with the link.

Today `knowledge-base/page.tsx` renders thirteen hardcoded categories from
`lib/mock/knowledge-base.ts`, and both of its dialogs close without saving
anything. There is no article body, no reader, no editor, and no API.

## 2. Scope

**In scope**

- `kb_categories` and `kb_articles`, scoped per workspace, with a
  draft → ready → published review workflow.
- A rich text editor in the console, storing structured documents rather
  than HTML.
- Image upload into articles, reusing slice 2's content-addressed blob
  storage.
- The public knowledge hub: index, category, article, and search pages,
  server-rendered on the workspace's portal subdomain.
- Postgres full-text search across both scopes in the console, and
  published external articles on the public hub.
- Subdomain-based workspace resolution for the whole `(portal)` route
  group — established here, inherited by the submit-ticket form when it is
  built.

**Not in scope**

- Importing articles by crawling a URL or uploading a file. The "Add source"
  dialog stays inert; it belongs with a later ingestion slice.
- AI retrieval, embeddings, or article suggestions. Slice 4 consumes what
  this slice stores; nothing here is AI-aware.
- The customer portal's authenticated surfaces — ticket lists, contact
  magic-link sessions. Everything public here is anonymous and read-only,
  which is precisely what keeps that work out of this slice.
- Article versioning or revision history.
- Per-article access control beyond the scope and status a workspace sets.
- Custom domains. A workspace is reachable at its subdomain of the
  deployment's portal domain, not at `help.acme.com`.

## 3. Decisions

**D1 — The editor stores structured documents, never HTML.** A rich editor
that persists HTML means storing user-supplied markup and re-rendering it on
the one surface anonymous visitors read. This slice stores the ProseMirror
document as JSON and renders it to HTML server-side from that known schema.
Three consequences, all of them the point: untrusted HTML never exists, so
there is nothing to sanitise; plain text extraction for search and for slice
4's grounding is a tree walk; and content survives a redesign, where a blob
of HTML is frozen in whatever markup the editor emitted. An unrecognised node
type renders as nothing.

**D2 — Scope lives on the category, not the article.** The console already
groups articles under separate internal and external category lists, so an
article's audience is a property of where it sits. Denormalising `scope` onto
both invites the two copies to drift.

**D3 — Statuses are a review workflow, meaning the same thing in both
scopes.** `draft` is being written, `ready` is reviewed and approved, and
`published` is live for that article's audience — publicly readable for
external, eligible for an agent to cite for internal. Transitions are a
separate endpoint from content updates, so saving a draft and putting
something in front of customers are never the same request.

**D4 — The portal is addressed by subdomain.** `acme.<portal domain>` serves
the whole customer-facing surface: the knowledge hub now, the submit-ticket
form when it is built. This matches the intent already recorded in
`app/(portal)/layout.tsx` and keeps one public origin per workspace.

**D5 — Image storage reuses slice 2's blob layer, not its table.**
`attachments.message_id` is required and an article image belongs to no
message, so a separate `kb_images` table is correct. The *storage* — content
addressing, the temp-write-and-rename, the containment-checked read — is
extracted into `services/blobs.py` and shared. That is a targeted refactor of
code this slice already touches, and it means slice 2's traversal fix
protects both paths rather than being reimplemented once per caller.

**D6 — Slugs are the public identifier.** Unique per `(workspace_id, scope)`
and stable across title edits, so renaming an article does not break a link a
customer has bookmarked or a search engine has indexed.

## 4. Deployment requirements

Stated here because leaving them implicit is how slice 2 shipped a poller
pointed at an empty mailbox.

**Wildcard DNS and a wildcard certificate** for the portal domain. Every
workspace is a subdomain of it, so `*.portal.example.com` must resolve to the
web tier and present a valid certificate. Without both, the public hub is
unreachable and nothing in the application explains why.

**Local development** uses `acme.localhost:3000`, which resolves without
hosts-file edits in Chrome, Firefox, and Safari.

**`PORTAL_DOMAIN`** is a new setting. In development it is `localhost:3000`.

## 5. Data model

Migrations continue from `0010`, starting at `0011`. Enums follow the
established pattern: `enum.StrEnum` with
`sa.Enum(..., native_enum=False, create_constraint=True)`.

**kb_categories** — `workspace_id`, `scope` (`internal` | `external`),
`name`, `slug`, `position` (integer, for manual ordering). Unique on
`(workspace_id, scope, slug)`. Indexed on `(workspace_id, scope, position)`.

**kb_articles** — `workspace_id`, `category_id` (required, `RESTRICT` on
delete so a category cannot be removed out from under its articles), `title`,
`slug`, `excerpt`, `doc` (JSONB — the ProseMirror document), `body_text`
(text — extracted plain text, maintained on write), `status`
(`draft` | `ready` | `published`), `author_user_id` (nullable, `SET NULL`),
`published_at` (nullable). Unique on `(workspace_id, category_id, slug)`.

`excerpt` is **authored, with a fallback**: if an author leaves it empty, the
API derives it from the first 200 characters of `body_text` on save. It is
never left blank, because it is what both the console list and the public
index render under each title.

**Search** is a generated column on `kb_articles`:
`search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', title || ' ' || coalesce(body_text, ''))) STORED`,
with a GIN index. `body_text` is written by the API from the document tree,
so the generated column stays a pure function of stored columns.

**kb_images** — `workspace_id`, `article_id` (required, `CASCADE`),
`filename`, `content_type`, `size_bytes`, `sha256`, `storage_key`. Indexed on
`article_id`.

**workspaces** gains nothing. `slug` already exists and is globally unique,
which is what makes it usable as a subdomain label.

## 6. Tenancy and subdomain resolution

A Next middleware reads the `Host` header, takes the first label, and rewrites
the request to an internal path carrying the workspace slug. The `(portal)`
layout resolves it through `GET /api/public/workspaces/{slug}`, a public
unauthenticated endpoint returning only the workspace's display name and
portal settings.

**Reserved labels.** `www`, `app`, `api`, `admin`, `mail`, and `inbound` never
resolve to a workspace, and workspace creation rejects them as slugs.
Otherwise registering the slug `api` takes over a hostname.

**The endpoint deliberately reveals which slugs exist.** That is inherent to a
public portal — the whole point is that `acme.<portal domain>` is reachable by
anyone. It returns display information only, never counts, member lists, or
anything about tickets.

**An unknown or reserved label renders a plain 404 page**, not a redirect to
the console, and not an error naming the deployment's other tenants.

## 7. Authoring

`/knowledge-base` keeps its current two-tab shape. "New article" creates a
`draft` row immediately and navigates to `/knowledge-base/{id}`, so an article
always has an id before anyone types — image upload needs something to attach
to.

The editor is TipTap, saving explicitly rather than autosaving. A knowledge
hub is reviewed content; silent autosave into a published article puts a
half-finished edit in front of customers the moment an author gets distracted.
Editing a published article keeps it published and does not move
`published_at`.

Toolbar: headings, bold, italic, lists, links, code blocks, blockquotes,
tables, horizontal rules, and images.

**Status transitions** are `POST /kb/articles/{id}/status` with a target
state, validated as a state machine: `draft → ready`, `ready → published`,
`published → draft`, and `ready → draft`. Publishing stamps `published_at`.
Any other transition is a `422`.

## 8. Images

Paste or drag uploads to `POST /kb/articles/{id}/images`, which stores the
bytes content-addressed and returns an id the editor writes into the document
node.

Served by `GET /api/kb/images/{id}`. Unlike message attachments, these are
**rendered inline** — that is what an image in an article is for — so the
route returns the stored content type only when it is on the image allowlist
established in slice 2 (`png`, `jpeg`, `gif`, `webp`; `svg+xml` deliberately
excluded because it executes script), and `application/octet-stream` with
`Content-Disposition: attachment` otherwise. `X-Content-Type-Options: nosniff`
on every response.

Console reads are workspace-scoped like every other domain route. **Public
reads are scoped to the article's visibility**: an image whose article is not
published external returns 404 on the public path, or an unpublished draft's
screenshots are readable by anyone who guesses an id.

## 9. The public hub

Four server-rendered routes under `(portal)`:

- `/help` — categories with published external articles, empty ones omitted.
- `/help/{category-slug}` — that category's published articles.
- `/help/{category-slug}/{article-slug}` — the article, rendered from JSON.
- `/help/search?q=` — full-text over published external articles.

Everything is anonymous and read-only. A `draft` or `ready` article returns
**404, not 403**, matching the tenancy convention and because confirming that
an unpublished article exists at a guessable slug is a small leak.

Rendering walks the document tree and emits HTML for known node types only.
An unknown node renders nothing rather than falling back to raw content.

## 10. API surface

Under `/api`, camelCase via `CamelModel`, bearer auth except where marked
public, and 404 rather than 403 for anything outside the caller's workspace.

```
GET    /kb/categories?scope=            -> [{ id, name, slug, position, articleCount }]
                                           articleCount counts every article in
                                           the category regardless of status —
                                           this is the console. The public index
                                           counts published only.
POST   /kb/categories                   { name, scope } -> CategoryOut          admin
PATCH  /kb/categories/{id}              { name?, position? } -> CategoryOut     admin
DELETE /kb/categories/{id}              -> 204                                  admin

GET    /kb/articles?scope=&status=&q=   -> [ArticleSummary]
POST   /kb/articles                     { categoryId, title } -> ArticleOut
GET    /kb/articles/{id}                -> ArticleOut
PATCH  /kb/articles/{id}                { title?, excerpt?, doc?, categoryId? } -> ArticleOut
POST   /kb/articles/{id}/status         { status } -> ArticleOut
DELETE /kb/articles/{id}                -> 204

POST   /kb/articles/{id}/images         multipart -> { id, url }
GET    /kb/images/{id}                  -> binary

GET    /public/workspaces/{slug}        -> { name, monogram }                   public
GET    /public/{slug}/kb                -> [CategoryWithArticles]               public
GET    /public/{slug}/kb/{cat}/{art}    -> ArticleOut                           public
GET    /public/{slug}/kb/search?q=      -> [ArticleSummary]                     public
```

Category delete is refused with `409` while it still holds articles, mirroring
`RESTRICT` on the foreign key rather than silently cascading a workspace's
documentation into nothing.

Deleting an article is permitted in any status and is a hard delete, taking its
images with it. Deleting a `published` external article breaks whatever links
point at it, so the console confirms before doing it; the API does not refuse,
because a workspace that wants a page gone — a mistaken publish, something
legally sensitive — must not have to unpublish first and then remember to come
back.

## 11. Web changes

- `knowledge-base/page.tsx` reads real data; `lib/mock/knowledge-base.ts` is
  deleted along with its `getKnowledgeBase`, `internalSuggestions`, and
  `externalSuggestions` exports.
- `knowledge-base/[id]/page.tsx` is new — the editor.
- `NewCategoryDialog` and `SourceDialog` stop closing without saving.
  `SourceDialog` remains inert but says so plainly rather than pretending.
- `(portal)` gains the four hub routes and a middleware for subdomain
  resolution; its layout resolves a real workspace instead of mock settings.
- `lib/types.ts`: `KbArticle` gains `slug`, `doc`, `categoryId`;
  `KbCategory` gains `slug`, `scope`, `position`.

## 12. Security

- Every domain query carries a `workspace_id` predicate; cross-workspace ids
  return 404, never 403.
- No user-supplied HTML is stored or rendered. Documents are JSON, rendered
  from a known schema (D1).
- Public reads are restricted to `published` articles in `external`
  categories; anything else is 404.
- Article images inherit their article's visibility on the public path.
- The image allowlist excludes SVG.
- Blob storage is content-addressed and containment-checked, inherited from
  slice 2 rather than reimplemented (D5).
- Reserved subdomain labels cannot be registered as workspace slugs.
- The public workspace endpoint returns display information only.

## 13. Testing

Following the established structure: async pytest against a real Postgres.

- **Document rendering** is a pure function over stored JSON — tested against
  fixtures including an unknown node type, deeply nested lists, and a node
  carrying an `onclick`-shaped attribute that must not survive.
- **Text extraction** feeds search and slice 4; tested for nesting and for
  documents with no text at all.
- **Tenancy:** a category, article, and image id from another workspace each
  404. A published external article in workspace A is not readable on
  workspace B's subdomain.
- **Visibility:** `draft` and `ready` articles 404 publicly; publishing makes
  the article readable and unpublishing makes it 404 again.
- **Status machine:** each legal transition succeeds, each illegal one 422s.
- **Slugs:** stable across a title change; collisions within a category
  rejected.
- **Search:** matches on title and body, excludes unpublished, excludes other
  workspaces.
- **Category delete** with articles present returns 409.

## 14. Build order

1. Migration `0011`, models, and the `services/blobs.py` extraction shared
   with slice 2's attachments.
2. Category service and API, with ordering.
3. Article service and API: create, read, update, delete, slugs.
4. The status state machine.
5. Document rendering and text extraction, as pure functions.
6. Search.
7. Image upload and serving.
8. Subdomain resolution: middleware, the public workspace endpoint, reserved
   labels.
9. The public hub's four routes.
10. The console list and the editor.

Steps 1 and 5 are early because everything else depends on them, and step 5
is pure, so it can be tested exhaustively before anything renders.

## 15. Known future consumers

**AI, slice 4.** Retrieval reads `body_text` and `doc` from published internal
articles. Nothing in this slice is AI-aware; adding embeddings means a new
column or table and no change to authoring.

**Portal, later.** The submit-ticket form and any authenticated customer
surface inherit the subdomain resolution established in section 6. Contact
sessions remain out of scope.

**Import.** A crawler or file importer produces the same `doc` JSON and reuses
the article service unchanged.

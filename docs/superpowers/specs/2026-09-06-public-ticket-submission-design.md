# Public ticket submission — design

**Date:** 2026-09-06
**Status:** approved in chat, pending written review
**Slice:** 4 (follows slice 3, the knowledge base)

## 1. What this builds

The customer-facing portal at `{slug}.<portal domain>` already serves a help
centre. It also serves a ticket form, but that form does not work: it calls
`preventDefault()` and shows a success message without sending anything
(`apps/web/components/portal/submit-ticket-form.tsx:52`). A customer is told
their message was received when it was not.

This slice makes the form real. An anonymous visitor submits a ticket, and it
lands in the workspace inbox indistinguishable from one that arrived by email
— same conversation model, same threading, same assignment, same reply path.

## 2. The trust shift, stated plainly

Every public surface built so far is a **read**. The knowledge base's public
API serves published articles and nothing else, and its whole design is about
making hidden content indistinguishable from absent content.

This is the first anonymous **write**. Untrusted input from the open internet
creates rows in the same tables the inbox reads. That is the reason this is
its own slice with its own spec rather than a form wired to an endpoint.

## 3. Decisions

**D1 — No email verification.** A submission creates the ticket immediately.
There is no confirmation link and no pending state.

The cost is accepted knowingly: the email address on the form is free text and
is never attested, so a submitter may type an address they do not control. An
agent replying to that ticket sends mail to the real owner of the address. A
double opt-in flow (submit → confirmation email → ticket created on click)
would close this and was considered and rejected in favour of lower friction.

Two consequences follow and are load-bearing for the rest of this design:

- The existing per-email hourly cap (`ingest._over_cap`) is weak here, because
  an attacker varies the address for free. It is still applied, but it is not
  the defence.
- **IP rate limiting becomes the primary abuse control**, not a secondary one.
  The API has none today.

**D2 — Submissions are marked as coming from the portal.** The conversation
records that it originated from the public form rather than from authenticated
email. This is provenance, not verification: it lets an agent see that the
address is unattested before replying to it, and it lets the inbox filter or
sort on it later. It costs one column.

**D3 — Attachments reuse the email-attachment path.** `attachments.store`
already enforces a content-type allowlist and a size cap, and writes through
the content-addressed blob layer with its traversal guard. The public path
reuses it rather than introducing a second upload implementation.

**D4 — One conversation per submission.** A submission always opens a new
conversation; it never threads into an existing one. Threading an anonymous,
unattested submission into a stranger's existing conversation would expose
that thread's contents to whoever guessed the address.

## 4. Flow

1. Visitor fills the form on `{slug}.<portal domain>/submit-ticket`.
2. Browser posts to the Next server, which forwards to
   `POST /api/public/{slug}/tickets`.
3. The API resolves the workspace from the slug — reserved labels and unknown
   slugs 404, exactly as the public knowledge base routes do.
4. Abuse controls run (section 6). A rejected submission returns a status the
   form can render without disclosing which control fired.
5. `contacts.upsert` resolves or creates the contact by email.
6. A conversation and its first inbound message are created, marked with the
   portal origin from D2.
7. Attachments, if any, are stored and linked.
8. The form shows a genuine confirmation.

## 5. API surface

```
POST /api/public/{slug}/tickets      multipart/form-data -> TicketSubmittedOut
```

Unauthenticated, consistent with the other `/api/public/{slug}/*` routes.
Request carries: `email` (required), `name`, `subject`, `message` (required),
zero or more `attachments`, and the honeypot field from section 6.

The response confirms receipt. It **does not** return the conversation id,
number, or any identifier that could be used to probe the inbox — the
submitter gets confirmation, not a handle.

Schemas live in `relaydesk/schemas/`, inherit `CamelModel`, and the service
raises `relaydesk.errors.*` rather than the router building envelopes.

## 6. Abuse controls

Layered, because no single one is sufficient once D1 removes verification.

- **IP rate limit** — a per-IP cap per window on this endpoint. New
  infrastructure; nothing in the API rate-limits today. The client IP must be
  taken from the proxy-forwarded header the deployment actually sets, and the
  plan must state which, because trusting the wrong one makes the limit
  bypassable by sending a header.
- **Honeypot field** — a form field hidden from humans; a submission that
  fills it is discarded. Cheap, and catches naive bots.
- **Per-email hourly cap** — `ingest._over_cap` is applied for consistency
  with email ingest. Weak here per D1, but free.
- **Message size cap** — the form advertises 10,000 characters; the API
  enforces it rather than trusting the client.
- **Attachment caps** — count per submission, and the existing per-file size
  cap and content-type allowlist from D3. `image/svg+xml` stays excluded.

A rejected submission must not tell the caller which control rejected it.

## 7. Multi-tenancy

Unchanged from every other slice and non-negotiable: every row carries
`workspace_id`, every query carries a `workspace_id` predicate, and a
cross-workspace identifier returns 404 rather than 403. The workspace comes
from the resolved slug in the path, never from a header or a form field.

## 8. Out of scope

- **Portal appearance settings.** The form's heading, blurb, submit label and
  consent text still come from `lib/mock/workspace`, and the console UI for
  them (`components/portal/ticket-form-settings.tsx`) writes nowhere. The form
  works with these as they are. Making them real is a separate piece.
- **Any reply surface for the submitter.** They receive no thread view and no
  status page. Replies reach them by email through the existing outbound path.
- **CAPTCHA.** The honeypot and IP limit are the bot controls in this slice.
- **Email verification**, per D1.

## 9. Testing

- The endpoint creates a conversation, contact, message and attachments, and
  the result is visible in the inbox exactly as an emailed ticket is.
- Every abuse control is proven by a test that fails if the control is
  removed — including that a rejected submission does not disclose the reason.
- A reserved label and an unknown slug both 404.
- A cross-workspace attempt cannot reach another tenant's inbox.
- An oversize message, an oversize attachment, a disallowed content type, and
  an `image/svg+xml` upload are each refused.
- The IP limit is tested against the header the deployment trusts, including
  that a client-supplied header cannot raise the caller's own allowance.

## 10. Known risks carried

- **Spoofed sender addresses** reach agents and receive replies (D1). Mitigated
  only by the provenance marker (D2) and agent judgement.
- **Anonymous disk writes.** Attachments from unauthenticated submitters
  consume storage, bounded by the per-file and per-submission caps but not by
  any per-IP storage budget.

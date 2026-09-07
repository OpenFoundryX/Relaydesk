# Password Reset — Design

**Date:** 2026-09-07
**Status:** approved in chat, pending written review
**Slice:** 5 (follows slice 4, public ticket submission)

**Sub-project 5 of the Relaydesk backend.** Builds on
`2026-09-04-tenancy-and-inbox-core-design.md` (slice 1), the binding
authority for users, sessions, memberships, and the API conventions, and on
`2026-09-04-email-channel-design.md` (slice 2), which built the mailer and
the system-email path this slice sends through. Where this document and
slice 1 disagree, section 3 records the amendment explicitly.

## 1. Goal

Give a user who has forgotten their password a way back into their account,
without an administrator and without anyone but the account's own mailbox
learning the secret that lets them in.

Relaydesk has no such path today. `api/auth.py` exposes `login`, `logout`,
the two Google routes, and `me` — nothing else. The only way a password is
ever set is `accept_invite`, which happens once. A user who forgets theirs
is locked out permanently unless an operator runs SQL against the users
table.

The absence is already load-bearing in the codebase's own reasoning:
`services/team.py:277` justifies part of the invite-acceptance rule on the
grounds that "there is no password-reset flow to recover from it losing."
Section 3 corrects that.

A second, smaller goal rides along: every system email Relaydesk sends is
plain text today, because nothing ever passes the `html_body` that
`mailer.build` and `send_system_email` have both accepted since slice 2.
This slice gives all three a shared HTML layout.

## 2. Scope

**In scope**

- A `password_resets` table, its Alembic migration, and the token lifecycle.
- `services/password_reset.py`: request and confirm.
- Two routes on `api/auth.py`, rate limited per IP and per address.
- Session revocation and lockout clearing on a completed reset.
- `notify_password_reset` alongside the two existing system emails.
- One shared HTML layout applied to all three system emails.
- Web: `forgot-password`, `reset-password`, and the link from login.

**Not in scope**

- Changing a password while signed in. It is a different flow with a
  different threat model — it authenticates on the current session and
  should require the existing password — and it does not block anyone out
  of their account, which is what this slice exists to fix.
- Email address change or verification.
- Any provider integration for system mail. Pointing `SMTP_*` at a real
  provider, and an HTTP-API adapter behind the mailer, are the next slice.
  See section 10.
- Multi-factor authentication, and account recovery for a user whose
  mailbox itself is lost.
- Anything for contacts on the customer portal. Contacts have no accounts
  and no passwords: the portal is anonymous and read-only, and the
  magic-link contact sessions slices 1 and 2 both anticipated have not been
  built. This slice is about `users` only.

## 3. Amendments to slice 1's spec

**A1 — the invite-adoption rationale.** `accept_invite`'s docstring gives
two reasons for overwriting `name` and `password_hash` on an *unclaimed*
user row: the squatting defense, and "there is no password-reset flow to
recover from it losing."

The second clause becomes false with this slice. **The behaviour does not
change** — adopting unclaimed rows is still correct, and the squatting
defense laid out in the same docstring is the real and sufficient reason
for it. Only the stated rationale is wrong, and leaving it would leave a
future reader believing a recovery path is missing when it is not. The
docstring is corrected as part of this slice's work, not left to drift.

## 4. Decisions

**D1 — a Google-only account cannot reset.** A user whose `password_hash`
is `NULL` receives no mail. The endpoint still answers `202`, identically
to every other input, so it cannot be used to discover which addresses are
Google-only.

The reasoning: such an account has never had a password, and its root of
trust is Google. Letting a reset mint one would mean control of the mailbox
alone is enough to obtain a Relaydesk password on an account that
deliberately has none — converting a Google-only account into a
password-able one without its owner doing anything.

The accepted cost is real and should be stated plainly: a user whose Google
access lapses has no self-serve recovery, and gets no explanation, because
explaining would defeat the uniform response. They need an operator. This
is judged acceptable while Google is the only federated provider and while
`login_with_google` already refuses any address without an active
membership.

**D2 — one shared plain layout, no workspace branding.** A single HTML
layout for all three system emails: inline CSS, no images, no remote
assets, text alternative always present. Per-workspace branding is
deliberately excluded — it would require threading the workspace down into
`services/notifications.py`, which today receives only the formatted
pieces, and it buys nothing for a password reset, which is not about a
workspace at all.

**D3 — single-use by deletion, not by a consumed flag.** A used row is
deleted. This is `read_invite`'s rule and it is adopted deliberately: a
replayed token then looks exactly like a token that never existed, because
there is nothing left to tell them apart by. A `consumed_at` column would
preserve evidence that a given token was once valid, which is information
no caller has any reason to be given.

**D4 — one live token per user.** Issuing a reset deletes that user's
existing rows first. Without this, a user who clicks "forgot password"
four times has four simultaneously-valid tokens sitting in four separate
emails, and each additional copy is another chance for one to leak. The
newest link is the only one that works.

**D5 — a completed reset revokes every session.** See section 7.

## 5. Data model

One table, shaped like `invites` because it is the same kind of object: a
short-lived, mailed, hashed capability.

```python
class PasswordReset(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "password_resets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
```

`security/tokens.py` is reused unchanged: `generate_token()` for a 256-bit
URL-safe secret, `hash_token()` for the sha256 that is all that persists.
The plaintext exists in exactly two places — the response of
`generate_token()`, and the body of one email — and in neither a log line,
a response body, nor the database.

No `email` column. The row points at a user; the address is read from that
user when the mail is composed. Storing a copy would let the two disagree.

`ON DELETE CASCADE` so deleting a user cannot leave a live capability
pointing at nothing.

New setting: `password_reset_ttl_minutes: int = 60`.

## 6. Requesting a reset

`services.password_reset.request(session, email, ip_bucket)` returns `None`
on every path, including the ones that do nothing.

Order of operations, and it matters:

1. **Rate limit first.** `ratelimit.check` commits, which is why it comes
   before any write this function might otherwise want to roll back — the
   ordering `api/public.py:188` already documents. Two buckets are charged:
   `password_reset_ip` and `password_reset_email`.
2. Look up the user by email.
3. Send no mail, and return, when any of these hold:
   - no user row exists;
   - `user.password_hash is None` (D1);
   - the user has no active membership. Such a user cannot sign in at all —
     `auth.default_membership` refuses them — so a working reset link would
     lead somewhere they still cannot go.
4. Delete the user's existing `password_resets` rows (D4).
5. Insert a new row with `expires_at = now + password_reset_ttl_minutes`.
6. Commit.
7. `notifications.notify_password_reset(...)`, which enqueues through
   `queue.enqueue_system_email` and therefore cannot raise into the caller.

### 6.1 Rate limits

| Bucket                 | Key                                    | Limit    |
|------------------------|----------------------------------------|----------|
| `password_reset_ip`    | `services.client_ip.resolve(request)`  | 5 / hour |
| `password_reset_email` | the submitted address, lowercased      | 3 / hour |

Both settings-driven: `password_reset_ip_hourly_cap: int = 5`,
`password_reset_email_hourly_cap: int = 3`.

**The IP key must come from `services.client_ip.resolve`, not
`api.deps.client_ip`.** These are two different functions and only one of
them is a limiter key.

- `api.deps.client_ip` returns `request.client.host` — the immediate peer,
  nothing else. That is the right value for the record-keeping it does
  today on `sessions.ip`.
- `services.client_ip.resolve` honours `X-Forwarded-For` only from a peer
  in `TRUSTED_PROXY_IPS`, and buckets IPv6 on its `/64`.

The browser reaches the API through the Next server, so **every** request
arrives from the `web` container's address. Keyed on
`api.deps.client_ip`, the whole deployment would share one bucket: five
password resets per hour for all users combined, refusing the sixth real
person because five others already asked. Nothing would error and nothing
would log; the limiter would look like it was working, because it would be,
on one bucket. This is the same failure the README documents at length for
`TRUSTED_PROXY_IPS`, and it is repeated here because the wrong function is
the one with the more inviting name.

The `/64` bucketing matters for the same reason it does on the ticket form:
keyed on a full IPv6 address, one residential subscriber holds 2**64
buckets, which is the same as holding no limit.

### 6.2 Enumeration defense, and its limit

The uniform `202` is the primary defense. Every input — a real address, an
unknown one, a Google-only one, a member of no workspace, a malformed
string that still parses as an email — produces the same status, the same
empty body, and the same copy on the web page.

**There is a residual timing channel and this spec accepts it rather than
hiding it.** The path that sends mail does a delete, an insert, a commit,
and a broker publish that the silent paths do not. That is measurable in
principle.

It is not equalized with dummy work. The `_DUMMY_PASSWORD_HASH` trick in
`services/auth.py` is available there because the asymmetry is a single
argon2 call, and paying it unconditionally is both cheap and exact. The
asymmetry here is database writes and a broker round trip; faking those
convincingly means writing rows nobody reads, on a path an attacker
controls the trigger for, which is a worse thing to own than the channel it
closes.

The mitigation is the rate limit. Distinguishing two addresses through a
noisy timing difference needs repeated samples per address; five requests
per hour per IP, and three per hour per address, denies the sample volume.
An attacker with a large address pool defeats the IP limit but still meets
the per-address one.

This is a deliberate, bounded acceptance. If a future slice adds a cheap
uniform-cost path, it should close this.

## 7. Confirming a reset

`services.password_reset.confirm(session, token, password)`:

1. Resolve the row by `hash_token(token)`. Missing, or `expires_at <=
   now()` → `NotFound("This reset link is not valid.")`. One message for
   both, per D3.
2. `user.password_hash = hash_password(password)`.
3. `user.failed_login_count = 0` and `user.locked_until = None`. **A
   locked-out user must actually get in.** Forgetting a password and
   guessing at it are the same activity from `authenticate`'s point of
   view, so the user most likely to need a reset is disproportionately
   likely to have tripped the five-attempt lockout on the way here.
   Completing a reset without clearing it produces the worst possible
   outcome: a correct new password that is still refused, with the same
   `BAD_CREDENTIALS` message, for up to fifteen minutes.
4. Delete the `password_resets` row.
5. **Delete every `Session` row for this user** (D5).
6. Commit.

On D5, and the objection to it: revoking sessions logs the user out of
devices they are using happily, which is a real cost on a flow they may
have reached through simple forgetfulness rather than compromise. It is
accepted because the two cases are indistinguishable from the server, and
they are asymmetric. If the reset was forgetfulness, the cost is signing in
again on a few devices, with a password they have just chosen and
definitely know. If the reset was a response to a compromise, not revoking
means the attacker's session survives the exact action the user took to
evict them — and `session_ttl_days` defaults to 30, so it survives for up
to a month. Paying a small certain cost to avoid a large conditional one is
the right side of that trade.

The password minimum is `Field(min_length=8)`, reused from
`schemas/team.py:53` rather than restated, so the two ways a password can
be set cannot drift apart.

## 8. API surface

| Method | Path                            | Auth | Success |
|--------|---------------------------------|------|---------|
| POST   | `/auth/password-reset`          | none | `202`   |
| POST   | `/auth/password-reset/confirm`  | none | `204`   |

`POST /auth/password-reset` takes `{email}` and returns `202` with an empty
body, unconditionally — including when refused by the rate limiter. A `429`
would itself be a signal, and worse, it would be a signal an attacker can
provoke deliberately against a chosen address.

`POST /auth/password-reset/confirm` takes `{token, password}` and returns
`204`. It does not mint a session. Unlike `accept_invite`, which signs the
new user in because the token proved possession of an address that had no
account yet, a reset ends at the login page: the user has just chosen a
password and signing in with it confirms it works.

## 9. Notifications and the shared layout

`notifications.notify_password_reset(email, name, token)` sends to
`{web_url}/reset-password#{token}`.

**The token goes in the URL fragment.** A fragment is never transmitted to
any server, including Relaydesk's own, so it cannot land in an access log,
a proxy log, or a `Referer` header. This is not a new idea here — it is the
rule `notify_invite` already documents, and the mistake that rule was
written to replace (`/invites/{token}` as a path segment) is exactly the
mistake available again here.

A new `services/mail_templates.py` renders one layout to a `(text, html)`
pair:

```python
def render(
    *, heading: str, body: str, action_label: str | None = None,
    action_url: str | None = None, footer: str | None = None,
) -> tuple[str, str]:
```

Constraints, all of them chosen for deliverability and for not looking like
a phishing attempt: inline CSS only, no `<style>` block, no remote images,
no web fonts, no tracking pixel. The action renders as a real `<a>` styled
as a button, with the URL also present as text so a client that strips
links still shows it. The text alternative is the existing plain body,
unchanged in wording.

`mailer.build()` already promotes a message to `multipart/alternative` with
the text part first when handed an `html_body`, and `send_system_email`
already accepts and forwards one. Nothing in the transport changes; this
slice only starts passing the argument that has been there since slice 2.

All three system emails — invite, assignment, password reset — go through
`render`. Rewiring the two existing ones is in scope precisely so a single
layout does not immediately fork into three.

## 10. Relationship to the next slice

This slice deliberately does not touch transport. System mail continues to
go over the same `SMTP_*` configuration the ticket channel uses.

Two findings from the exploration that produced this document belong to the
next slice and are recorded here so they are not rediscovered:

- `mailer.py` passes `start_tls=settings.smtp_use_tls` to `aiosmtplib` and
  never sets the separate `use_tls` kwarg. `aiosmtplib` treats
  `start_tls=None` as "upgrade if offered" and `start_tls=False` as "never
  upgrade" — so the development default of `SMTP_USE_TLS=false`, carried
  into a real deployment, does not merely skip an optional upgrade, it
  actively refuses STARTTLS and attempts cleartext authentication. Implicit
  TLS on port 465 is unreachable entirely, since that requires `use_tls`.
- `mailer.from_address()` sends system mail from
  `noreply@{INBOUND_DOMAIN}`, and `INBOUND_DOMAIN` is required to be a
  catch-all. `noreply@` therefore receives mail into the same mailbox the
  IMAP poller reads.

## 11. Web changes

- `apps/web/app/(auth)/forgot-password/page.tsx` — an address field, and a
  confirmation that is identical whatever was typed.
- `apps/web/app/(auth)/reset-password/page.tsx` — reads the token from
  `window.location.hash` client-side, mirroring `app/invites`; a new
  password field with the same 8-character minimum; on success, redirect to
  login. The token is never put into component props that could be
  serialized into the HTML payload.
- A "Forgot password?" link on the login page.

## 12. Security

- The plaintext token exists in the `generate_token()` return value and in
  one email body. Never in a response, never in a log, never in the
  database, never in a URL path or query string.
- Uniform `202` on request, with the residual timing channel of section 6.2
  stated and bounded.
- Single-use by deletion; a replay is indistinguishable from a token that
  never existed.
- One live token per user.
- One hour TTL.
- A completed reset clears the login lockout and revokes every session.
- The rate-limit key comes from the trusted-proxy-aware resolver, per
  section 6.1.
- No mail to an account with no password (D1) and none to an account that
  cannot sign in.

## 13. Testing

- Request for an unknown address → `202`, nothing enqueued, no row written.
- Request for a Google-only account → `202`, nothing enqueued.
- Request for a user with no active membership → `202`, nothing enqueued.
- Request for a real user → `202`, exactly one email enqueued, and the
  token appears in that email and in no response body.
- A second request invalidates the first token (D4): the first now 404s.
- Confirm with a valid token → password changed, row deleted, every session
  for that user gone, `failed_login_count` zeroed, `locked_until` cleared.
- A user locked out by five failed logins can reset and log in immediately.
- Replay of a consumed token → `404`, byte-identical to a token that never
  existed.
- Expired token → `404`.
- Confirm with a password under 8 characters → `422`.
- The sixth request from one IP bucket in an hour → still `202`, and
  nothing enqueued.
- Two requests from different IPs land in different `rate_limit_hits` keys —
  the regression test for using the wrong `client_ip`.
- All three system emails carry both a `text/plain` and a `text/html` part,
  text first.

## 14. Build order

1. Model, migration, settings.
2. `services/mail_templates.py` and the rewiring of the two existing
   system emails. Independent of everything below, and it puts the layout
   under test before a security-sensitive flow depends on it.
3. `services/password_reset.py` — request and confirm, with unit tests.
4. `notifications.notify_password_reset`.
5. Routes, schemas, and rate limiting.
6. The `accept_invite` docstring correction (A1).
7. Web pages and the login link.
8. README: the reset flow, and the new settings.

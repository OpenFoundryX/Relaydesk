# Relaydesk

Open-source AI-native customer support.

Relaydesk is building an open platform for modern customer support, with a
self-hostable codebase and a managed cloud offering. The project is currently
in its initial development stage.

## Project status

Relaydesk is under active early development. Workspaces, sign-in (including
Google), team management, and the ticket inbox — conversations, replies,
labels, saved views, and activity history — are implemented on a
multi-tenant Next.js, FastAPI, and PostgreSQL foundation. Email is a fully
working channel: mail forwarded to a workspace's ingest address becomes a
ticket, replies are delivered over SMTP with retry and bounce handling, and
attachments are stored and served back safely. The knowledge base lets a
workspace write and publish help articles, with a public help site anonymous
customers can read and search. Discord, one-click import from another help
desk, AI features, analytics, and billing are not yet implemented.

Team invites are sent by email: accepting one lets you choose an account's
password and sign in as it, so the invite link is only ever mailed to the
invited address, never returned to whoever created the invite. This means
invites require SMTP to be configured — the development stack provides
this out of the box via GreenMail.

A user who forgets their password can recover it themselves: **Forgot
password?** on the sign-in page mails a single-use link that expires in an
hour. Like invites, the link is only ever mailed to the address it belongs
to, so this also requires SMTP to be configured — the development stack
provides it through GreenMail.

Two behaviours are deliberate and will look like bugs otherwise:

- **The page says the same thing whatever you type.** A different answer
  for an address that has no account would turn the form into a way to
  discover who has one.
- **An account that only signs in with Google gets no reset mail**, and is
  told no differently. Such an account has never had a password and its
  root of trust is Google; minting one from mailbox control alone would
  convert it into a password account without its owner doing anything. A
  Google-only user who loses Google access can still be recovered: an
  admin removes them from the workspace, which leaves their account
  unclaimed, and inviting the same address again lets them adopt it and
  choose a password when they accept. The exception is a sole admin — the
  workspace refuses to remove its last remaining admin, so a Google-only
  admin with no co-admin who loses Google access needs direct database
  access instead.

Completing a reset signs the user out everywhere. If the reset was the
answer to a compromise, leaving the other sessions alive would let the
attacker outlast the eviction by up to `SESSION_TTL_DAYS`.

## Requirements

- Docker
- Docker Compose

## Start

```sh
git clone <repository-url> relaydesk
cd relaydesk
cp .env.example .env
docker compose up --build
```

Then visit:

- Web: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Google sign-in (optional)

"Continue with Google" on the login page works out of the box for
self-hosters who don't configure it: the button redirects back to sign-in
with an error banner instead of crashing. To enable it, set
`GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` from a Google Cloud
OAuth client, and register `http://localhost:3000/login/google/callback` as
an authorized redirect URI in the Google Cloud console. There is no
self-serve signup through Google — an email must already have an active
membership to sign in.

## Demo data

```sh
make seed
```

Seeds a demo workspace with two users, four labels, and eleven tickets across
every status. Sign in as `nilesh@relaydesk.dev` with the password `relaydesk`.

## Self-hosting your own workspace

```sh
read -rsp "Admin password: " RELAYDESK_ADMIN_PASSWORD
export RELAYDESK_ADMIN_PASSWORD
docker compose exec -e RELAYDESK_ADMIN_PASSWORD api relaydesk bootstrap \
  --workspace "Acme Support" \
  --email you@acme.com \
  --name "Your Name"
```

The admin password is read from `RELAYDESK_ADMIN_PASSWORD`. There is a
`--password` flag as a fallback, but prefer the environment variable: a
password in the command line is visible to anyone who can run `ps` on the
host and is written to your shell history.

### Inbound email

Every workspace gets a distinct ingest address (`<slug>-<token>@INBOUND_DOMAIN`),
but all of them must land in the single mailbox the IMAP poller reads — so
`INBOUND_DOMAIN` must be configured as a catch-all at your mail provider. A
provider that files each address into its own mailbox will silently drop
every ticket, with no error.

Find a workspace's address under **Settings → Channels**, then forward your
own support address to it. Anything that arrives there becomes a ticket.

### Password reset

`PASSWORD_RESET_TTL_MINUTES` (default 60), `PASSWORD_RESET_IP_HOURLY_CAP`
(default 5) and `PASSWORD_RESET_EMAIL_HOURLY_CAP` (default 3) bound the
flow. The caps are low on purpose: they are what makes the timing
difference between "this address has an account" and "it does not"
impractical to measure, since the uniform response does not by itself
erase it.

## Knowledge base

Articles live in one of two scopes:

- **Internal** — procedures for the AI agent, describing how to handle a
  kind of request step by step. Never shown to a customer.
- **External** — the customer-facing help site, written as if speaking
  directly to a customer.

Every article moves through the same review workflow: **draft** while it is
being written, **ready** once it is written but held back, and **published**
once it should go live. Only a published article in an external category is
ever served to an anonymous visitor; a draft or ready article at a guessable
URL 404s exactly like one that never existed.

Published external articles are served at
`<slug>.<portal domain>/help`, with per-category pages, per-article pages,
and full-text search. **Deployment requirement:** the portal domain needs
wildcard DNS (`*.<portal domain>`) pointed at the app and a wildcard TLS
certificate covering it, since every workspace gets its own subdomain
resolved at request time. In local development this is already handled:
`PORTAL_DOMAIN` defaults to `localhost:3000`, and every workspace is reached
at `<slug>.localhost:3000` (e.g. `http://chronon.localhost:3000/help`)
without any DNS or certificate setup, because browsers resolve
`*.localhost` to the loopback address on their own.

## Public ticket submission

Every workspace's portal has a ticket form at `<slug>.<portal domain>/submit-ticket`,
backed by `POST /api/public/{slug}/tickets`. A submission there lands in the
console inbox exactly like an emailed one, tagged with the `portal` channel.
A `company` field on the form is a honeypot: it is hidden from a human with
CSS (not `type="hidden"`, which a scraper checks for and skips), and filling
it gets the same `201` a real submission gets, so a bot never learns it was
caught.

### `TRUSTED_PROXY_IPS`

**If this does not name the address of the container in front of the API —
the `web` service — the whole feature's abuse control is gone, silently.**

The browser posts to the Next server, which calls the API on the customer's
behalf, so every submission reaches the API from the same peer. The visitor's
own address travels as `X-Forwarded-For`, and the API believes that header
only from a peer listed here. Get it wrong and every visitor on earth resolves
to the `web` container's address, which means the entire product accepts
**five portal tickets per hour, total** — the next customer to try is refused
because someone else already submitted. Nothing errors, nothing logs; the
limiter looks like it is working, because it is, on one bucket.

There is no email verification on this form: the submitter's address is free
text and never attested, so the per-email cap is evaded by varying it. That
makes the IP limit the only real abuse control there is, which is why this
setting is worth this much of the README.

In `docker-compose.yml` the `web` service is pinned to a static
`ipv4_address` (`172.20.255.8`) on a network with a fixed subnet, and
`TRUSTED_PROXY_IPS` for `api` defaults to that same address. Both halves are
fixed by that file rather than handed out by Docker's allocator, so they
cannot drift apart across `docker compose down && up`. If you change one,
change the other. In a deployment that is not this Compose stack, set
`TRUSTED_PROXY_IPS` to whatever address the API actually sees your proxy
arrive from — `docker network inspect <project>_default`, or the peer address
in your ingress logs — and verify it: submit two tickets from two different
addresses and check that `rate_limit_hits` has two distinct `key` values.

### A reverse proxy in front of Next

`apps/web/middleware.ts` deletes the incoming `x-forwarded-for` header
unconditionally, and relies on Next re-filling it from the socket address
(Next does `req.headers['x-forwarded-for'] ??= socket.remoteAddress`, so it
only fills the header in when it is absent). That is what stops a caller
sending its own `X-Forwarded-For` and picking its own rate-limit bucket per
request.

**It also means that if you put a TLS terminator, load balancer, or CDN in
front of the Next server, its genuine client chain is discarded** and
replaced with that proxy's own address — so every visitor once again shares
one bucket, in exactly the shape described above. Next is assumed here to be
the outermost hop. If it is not, the strip in `middleware.ts` has to become
selective: keep the forwarded chain when the connection came from a proxy you
trust, and take the client from it, rather than deleting it outright.

## Development commands

```sh
make dev               # Build and start the development stack
make down              # Stop the stack
make logs              # Follow service logs
make clean             # Stop the stack and remove its development volumes
make seed              # Fill the database with demo data
make migrate           # Run pending Alembic migrations
make revision m="..."  # Autogenerate a new Alembic migration
```

API source and web source are bind-mounted into their development containers, so
changes are picked up without rebuilding the images.

Besides `postgres`, `api`, and `web`, the stack runs four more services for
the email channel: `rabbitmq` (the Celery broker), `worker` (a Celery worker
that polls IMAP and delivers replies over SMTP), `beat` (schedules the
recurring IMAP poll and the retry/reconciliation jobs), and `greenmail` (a
local SMTP/IMAP server standing in for a real mail provider). `docker
compose logs -f worker beat` follows the mail pipeline specifically.

## Testing and linting

With the development stack running:

```sh
docker compose exec api pytest -m "not integration"
docker compose exec api ruff check .
docker compose exec web pnpm lint
docker compose exec web pnpm build
```

Tests marked `integration` exercise a live service in the compose stack (for
example, a real round trip through GreenMail) and are excluded by default.
Run them explicitly, with the stack up, via:

```sh
docker compose exec api pytest -m integration
```

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a pull request. By participating, you agree to follow the
[Code of Conduct](CODE_OF_CONDUCT.md).

- Report bugs and request features through GitHub issues.
- Ask usage and development questions as described in [SUPPORT.md](SUPPORT.md).
- Report vulnerabilities privately by following [SECURITY.md](SECURITY.md).
- Project decisions and maintainer responsibilities are described in
  [GOVERNANCE.md](GOVERNANCE.md).

## License

Relaydesk is licensed under the [GNU Affero General Public License v3.0
only](LICENSE). If you modify Relaydesk and make it available to users over a
network, the AGPL requires you to offer those users the corresponding source
code for your modified version.

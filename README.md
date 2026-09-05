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
attachments are stored and served back safely. Discord, one-click import
from another help desk, AI features, the knowledge base, analytics, and
billing are not yet implemented.

Team invites are sent by email: accepting one lets you choose an account's
password and sign in as it, so the invite link is only ever mailed to the
invited address, never returned to whoever created the invite. This means
invites require SMTP to be configured — the development stack provides
this out of the box via GreenMail.

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

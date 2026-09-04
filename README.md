# Relaydesk

Open-source AI-native customer support.

Relaydesk is building an open platform for modern customer support, with a
self-hostable codebase and a managed cloud offering. The project is currently
in its initial development stage.

## Project status

Relaydesk is under active early development. Workspaces, sign-in (including
Google), team management, and the ticket inbox — conversations, replies,
labels, saved views, and activity history — are implemented on a
multi-tenant Next.js, FastAPI, and PostgreSQL foundation. Channels beyond the
seeded demo data, AI features, the knowledge base, analytics, and billing are
not yet implemented.

Team invites are sent by email: accepting one lets you choose an account's
password and sign in as it, so the invite link is only ever mailed to the
invited address, never returned to whoever created the invite. This means
invites require SMTP to be configured — the development stack provides
this out of the box via GreenMail, so invites work with no extra setup when
running through Docker Compose.

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

## Testing and linting

With the development stack running:

```sh
docker compose exec api pytest
docker compose exec api ruff check .
docker compose exec web pnpm lint
docker compose exec web pnpm build
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

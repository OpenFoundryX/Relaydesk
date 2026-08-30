# Contributing to Relaydesk

Thanks for helping improve Relaydesk. Contributions of code, documentation,
bug reports, and design feedback are welcome.

## Before you start

- Search existing issues before opening a new one.
- Use an issue to discuss significant features or architectural changes before
  investing in an implementation.
- Keep pull requests focused. Avoid combining unrelated changes.
- Do not include secrets, customer data, or generated dependency directories.

## Development setup

Requirements:

- Docker
- Docker Compose

Start the development stack:

```sh
cp .env.example .env
docker compose up --build
```

The services are available at:

- Web: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

See [README.md](README.md) for the complete local development commands.

## Making a change

1. Fork the repository and create a branch from the default branch.
2. Make the smallest change that solves the issue.
3. Add or update tests when behavior changes.
4. Update documentation when configuration or developer workflows change.
5. Run the checks below.
6. Open a pull request and complete the pull request template.

## Required checks

With the stack running:

```sh
docker compose exec api ruff check .
docker compose exec api pytest
docker compose exec web pnpm lint
docker compose exec web pnpm build
```

## Code expectations

- Follow the existing project structure and conventions.
- Prefer clear, typed interfaces and minimal dependencies.
- Keep the initial architecture simple; avoid speculative abstractions and
  placeholders for unimplemented features.
- Format Python consistently with Ruff's defaults.
- Keep TypeScript in strict mode and resolve ESLint errors.
- Never commit `.env` files or credentials.

## Commits and pull requests

Write concise, imperative commit messages. Pull requests should explain the
problem, the chosen solution, how it was tested, and any user-visible impact.
Link the relevant issue when one exists.

Maintainers may ask for a pull request to be split when independent concerns
would be easier to review separately.

## Licensing of contributions

By submitting a contribution, you agree that it may be distributed under the
GNU Affero General Public License v3.0 only, the license covering this project.
You must have the right to submit the contribution.

Participation in this project is governed by the
[Code of Conduct](CODE_OF_CONDUCT.md).

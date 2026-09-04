.PHONY: dev down logs clean seed migrate revision

dev:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down --volumes --remove-orphans

seed:
	docker compose exec api relaydesk seed

migrate:
	docker compose exec api alembic upgrade head

revision:
	docker compose exec api alembic revision --autogenerate -m "$(m)"

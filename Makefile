.PHONY: dev down logs clean

dev:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down --volumes --remove-orphans

# Makefile
.PHONY: help build up down dev logs logs-back logs-front logs-db ps shell-back shell-front shell-db test migrate makemigration downgrade

ENV_FILE := .env

help:
	@echo "Targets:"
	@echo "  make build       Build docker images (prod)"
	@echo "  make up          Start containers (prod: docker compose.yml)"
	@echo "  make dev         Start dev environment (docker compose up with override)"
	@echo "  make down        Stop and remove containers"
	@echo "  make logs        Follow logs"
	@echo "  make logs-back   Follow backend logs only"
	@echo "  make logs-front  Follow frontend logs only"
	@echo "  make ps          List containers"
	@echo "  make shell-back  Open shell in backend container"
	@echo "  make shell-front Open shell in frontend container"
	@echo "  make shell-db    Open psql in the postgres container"
	@echo "  make test        Run backend tests (containerized)"
	@echo "  make migrate     Apply pending DB migrations (alembic upgrade head)"
	@echo "  make makemigration m=\"msg\"  Autogenerate a migration from model changes"
	@echo "  make downgrade   Roll back one DB migration"
	@echo "  make clean       Remove images (dangerous)"

build:
	docker compose build --parallel

up:
	docker compose up -d

dev:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

logs-back:
	docker compose logs -f backend

logs-front:
	docker compose logs -f frontend

ps:
	docker compose ps

shell-back:
	docker compose exec backend /bin/sh

shell-front:
	docker compose exec frontend /bin/sh

test:
	docker compose exec backend pytest -q

shell-db:
	docker compose exec db psql -U $${POSTGRES_USER:-recitroc} $${POSTGRES_DB:-recitroc}

migrate:
	docker compose exec backend alembic upgrade head

makemigration:
	docker compose exec backend alembic revision --autogenerate -m "$(m)"

downgrade:
	docker compose exec backend alembic downgrade -1

clean:
	docker compose down --rmi all --volumes --remove-orphans

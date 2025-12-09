# Makefile
.PHONY: help build up down dev logs ps shell-back shell-front test

ENV_FILE := .env

help:
	@echo "Targets:"
	@echo "  make build      Build docker images (prod)"
	@echo "  make up         Start containers (prod: docker compose.yml)"
	@echo "  make dev        Start dev environment (docker compose up with override)"
	@echo "  make down       Stop and remove containers"
	@echo "  make logs       Follow logs"
	@echo "  make ps         List containers"
	@echo "  make shell-back  Open shell in backend container"
	@echo "  make shell-front Open shell in frontend container"
	@echo "  make test       Run backend tests (containerized)"
	@echo "  make clean      Remove images (dangerous)"

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

ps:
	docker compose ps

shell-back:
	docker compose exec backend /bin/sh

shell-front:
	docker compose exec frontend /bin/sh

test:
	docker compose exec backend pytest -q

clean:
	docker compose down --rmi all --volumes --remove-orphans

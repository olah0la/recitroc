# Recitroc

*Bartering in the 21st century.*

Recitroc is a goods and services bartering app based on user geolocation. The goal is to strengthen local community bonds through the exchange of goods and services. Users express what they need from the community — and what they can offer in return. Recitroc's gamification of this exchange is what makes it special.

## Features

- **Matching** — During onboarding, users express their needs (a service like language conversation exchange, or goods like a bike or a sofa) and what they can offer. No currency values are assigned — that goes against the spirit of barter and community building. Instead, users are matched based on complementary needs and offers in their area.
- **Swipe-based discovery** — Browse potential exchanges nearby with a familiar swipe interface.
- **Messaging** — Chat with your matches to arrange the exchange.

## Tech stack

- **Frontend**: React + TypeScript (Vite)
- **Backend**: FastAPI (Python 3.11) with SQLAlchemy and Alembic migrations
- **Database**: PostgreSQL 16
- **Infrastructure**: Docker Compose with nginx-proxy for path-based routing

## Getting started

Prerequisites: Docker and Docker Compose.

```bash
cp .env.example .env   # adjust values if needed
make dev               # build and start the dev environment (hot reload)
```

Then open:

- Frontend: http://recitroc.localhost/
- API docs: http://recitroc.localhost/api/docs

## Development

Common commands (see `make help` for the full list):

```bash
make test                       # run backend tests (pytest, containerized)
make logs                       # follow all logs (logs-back / logs-front for one service)
make migrate                    # apply pending DB migrations
make makemigration m="message"  # autogenerate a migration from model changes
make shell-back                 # shell into the backend container
make shell-db                   # psql prompt in the postgres container
make down                       # stop containers
```

Backend code follows a layered architecture (api → crud → models → db); see [CLAUDE.md](CLAUDE.md) for a detailed tour. Pre-commit hooks (black, isort, ruff) are configured — install them with `pre-commit install`.

# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# system deps (if any). e.g. build-essential for some packages:
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements first so Docker's layer cache skips the (slow) pip
# install whenever only application code changed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Migrations ship inside the image: any container can run
# `alembic upgrade head` (compose does this on startup).
COPY alembic.ini .
COPY ./alembic ./alembic
COPY ./app ./app

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# In prod: run without --reload. We use Uvicorn as entrypoint.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

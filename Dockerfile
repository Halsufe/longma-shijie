FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 gcc libpq-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/app /app/backend/app
COPY backend/__init__.py /app/backend/__init__.py
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY frontend /app/frontend
RUN mkdir -p /app/backend/storage

EXPOSE 7860
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]

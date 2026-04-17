# Production Control

Минимальный bootstrap проекта для сервиса управления производством на `FastAPI`, `Poetry` и `Docker Compose`.

## Требования

- Python 3.11
- Poetry
- Docker и Docker Compose

## Локальный запуск через Poetry

```bash
poetry env use 3.11
poetry install
poetry run uvicorn src.app.main:app --reload
```

Проверка:

```bash
curl http://localhost:8000/health
```

## Запуск через Docker Compose

```bash
copy .env.example .env
docker compose up --build
```

Проверка:

```bash
curl http://localhost:8000/health
```

## Сервисы инфраструктуры

- API: `http://localhost:8000`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- RabbitMQ AMQP: `localhost:5672`
- RabbitMQ UI: `http://localhost:15672`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`

## Полезные команды

```bash
poetry run pytest
poetry run ruff check .
poetry run mypy src
```

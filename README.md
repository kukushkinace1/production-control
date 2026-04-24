# Production Control API

FastAPI service for production batch control: batches, products, aggregation,
reports, import/export, webhooks, Redis cache, analytics, and scheduled
maintenance jobs.

## Stack

- Python 3.11
- FastAPI, Pydantic v2
- SQLAlchemy 2 async, Alembic
- PostgreSQL 16
- RabbitMQ, Celery, Celery Beat
- Redis for cache and Celery result backend
- MinIO for S3-compatible file storage
- Docker Compose

## Local Setup

```powershell
copy .env.example .env
docker compose up --build
```

The compose stack includes a one-shot `migrate` service that runs:

```bash
alembic upgrade head
```

## Service URLs

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- RabbitMQ UI: http://localhost:15672
- MinIO Console: http://localhost:9001
- Flower: http://localhost:5555

Default MinIO credentials:

```text
minioadmin / minioadmin
```

## Useful Commands

```powershell
poetry install
poetry run pytest
poetry run ruff check src tests
poetry run alembic upgrade head
```

Run only app locally:

```powershell
poetry run uvicorn src.main:app --reload
```

## Smoke Checks

Health:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/health/db
```

Dashboard analytics:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/analytics/dashboard
```

Batch statistics:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/batches/1/statistics
```

Compare batches:

```powershell
$body = @{ batch_ids = @(1, 2, 3) } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/analytics/compare-batches `
  -ContentType application/json `
  -Body $body
```

Call scheduled tasks manually:

```powershell
docker compose exec celery_worker celery -A src.celery_app:celery_app call src.tasks.scheduled.auto_close_expired_batches
docker compose exec celery_worker celery -A src.celery_app:celery_app call src.tasks.scheduled.cleanup_old_files
docker compose exec celery_worker celery -A src.celery_app:celery_app call src.tasks.scheduled.update_cached_statistics
docker compose exec celery_worker celery -A src.celery_app:celery_app call src.tasks.scheduled.retry_failed_webhooks
```

Watch Celery Beat:

```powershell
docker compose logs -f celery_beat
```

Check Redis cache keys:

```powershell
docker compose exec redis redis-cli KEYS *
docker compose exec redis redis-cli GET dashboard_stats
```

## Implemented Features

- Batch and product CRUD
- Sync and async product aggregation
- Task status endpoint
- Excel and PDF batch reports in MinIO
- CSV/XLSX batch import and export
- Webhook subscriptions, delivery history, HMAC signatures, retry
- Redis caching with invalidation
- Dashboard analytics, batch statistics, batch comparison
- Celery Beat maintenance tasks
- Flower monitoring
- Basic Redis-backed rate limiting

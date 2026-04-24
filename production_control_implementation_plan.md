# План реализации проекта: система контроля заданий на выпуск продукции

## 0. Что это за проект на самом деле

Это не просто CRUD на FastAPI. По факту это **production management backend** с четырьмя контурами:
1. **Операционный контур** — партии, продукция, рабочие центры, фильтрация, аналитика.
2. **Асинхронный контур** — Celery-задачи, длительные операции, импорты/экспорты/отчёты.
3. **Интеграционный контур** — webhooks, MinIO, внешние получатели событий.
4. **Инфраструктурный контур** — Postgres, Redis, RabbitMQ, Docker Compose, миграции, мониторинг.

Если попытаться делать всё подряд без этапов, почти гарантированно получится каша: сломанные миграции, нестабильные celery workers, неясный контракт API, и куча несвязанных коммитов. Поэтому тебе нужен **вертикальный, но управляемый инкрементальный план**: сначала собрать платформу, потом домен, потом асинхронку, потом интеграции, потом аналитические и фоновые фичи.

---

# 1. Двойной анализ перед стартом

### Первый анализ: что обязательно для рабочего MVP

Без чего проект не взлетит вообще:
- базовый каркас приложения FastAPI + Poetry + settings + Dockerfile + docker-compose;
- PostgreSQL + async SQLAlchemy + Alembic;
- доменные модели `WorkCenter`, `Batch`, `Product`;
- базовые CRUD ручки для партий и продукции;
- нормальная структура слоёв: API / service / repository / db / core;
- healthcheck и базовый smoke test;
- один рабочий Celery worker + broker + result backend;
- endpoint для запуска асинхронной задачи + endpoint для статуса задачи.

То есть реальный MVP — это не все 100% требований, а **устойчивая основа**, на которую дальше без боли навешиваются импорт/экспорт/webhooks/кэш.

### Второй анализ: что опасно и где чаще всего ломаются такие проекты
Критичные риски:
1. **Слишком ранний Celery**. Если поднимать Celery до того, как у тебя устоялись модели, сервисы и транзакции, потом придётся переписывать таски и импортировать половину приложения циклически.
2. **Смешение sync и async**. API у тебя async, SQLAlchemy async, но Celery worker чаще делает sync-обвязку либо запускает async-код через отдельные helper-обёртки. Это надо продумать сразу.
3. **MinIO и отчёты раньше времени**. Генерация файлов кажется простой, но на деле там временные файлы, cleanup, content-type, presigned URL, ошибки записи, удаление мусора.
4. **Webhooks без outbox-like подхода**. Нельзя просто “после создания партии отправить HTTP”. Правильнее создавать запись delivery в БД и отправлять её отдельной задачей.
5. **Кэш без инвалидации**. Если сначала накрутить Redis, а потом руками пытаться догонять invalidation, можно запутаться. Кэш надо добавлять после стабилизации CRUD.
6. **Слишком большой первый PR**. За 2 дня это особенно опасно. Нужны маленькие PR с явным критерием готовности.

# 4. Git-стратегия и как вести PR

### Основная идея

Не работай в `main`.

Схема:
- `main` — всегда стабилен, всё, что там, должно подниматься.
- каждая фича — отдельная ветка от `main`;
- один логический PR = один законченный checkpoint.

### Нейминг веток

```bash
feature/bootstrap-project
feature/setup-db-and-alembic
feature/batches-crud
feature/products-and-aggregation
feature/celery-task-status
feature/reports-minio
feature/import-export
feature/webhooks
feature/cache-analytics
feature/scheduled-tasks
```

### Нейминг коммитов

Лучше в стиле conventional-ish, но без фанатизма:

```bash
feat: bootstrap fastapi project with poetry and docker
feat: add async sqlalchemy models and alembic migrations
feat: implement batches CRUD and filters
feat: add product creation and sync aggregation endpoint
feat: integrate celery and task status endpoint
feat: add report generation and minio upload
feat: implement import and export tasks
feat: add webhook subscriptions and delivery retries
feat: add redis cache and analytics endpoints
chore: add docker healthchecks and make commands
fix: invalidate batch cache after aggregation
test: add integration tests for batches API
```

### Размер PR

Нормальный PR за этот проект — **200–600 строк meaningful diff**. Если у тебя выходит 1500+ строк и 20 файлов сразу, ты уже делаешь себе боль.

### Шаблон PR-описания

```md
## Что сделано
- ...
- ...

## Что не сделано
- ...

## Как проверить локально
1. ...
2. ...
3. ...

## Риски / caveats
- ...
```

---

# 5. Порядок разработки по этапам и PR-чекпоинтам

Ниже — оптимальный маршрут именно под задачу “сделать за ~2 дня и фиксировать checkpoints”.

---

## Этап 1. Bootstrap проекта

## Цель
Собрать минимально живой каркас: Poetry, FastAPI, Docker, docker-compose, env, healthcheck, базовый запуск.

## Ветка
```bash
git checkout -b feature/bootstrap-project
```

## Что делаем
1. Создаёшь проект через Poetry.
2. Выставляешь Python 3.11.
3. Добавляешь зависимости.
4. Делаешь базовую структуру каталогов.
5. Поднимаешь `FastAPI app`, `/health` endpoint.
6. Добавляешь `Dockerfile`, `docker-compose.yml` с api + postgres + redis + rabbitmq + minio, даже если часть ещё не используется.
7. Добавляешь `.env.example`.
8. Добавляешь `README` с командами запуска.

## Poetry зависимости

```bash
poetry init
poetry env use 3.11
poetry add fastapi uvicorn[standard] pydantic pydantic-settings sqlalchemy asyncpg alembic
poetry add celery redis aio-pika httpx minio openpyxl pandas python-multipart
poetry add tenacity structlog
poetry add --group dev pytest pytest-asyncio pytest-cov ruff mypy httpx faker
```

Минимум можно начать даже без `pandas`, если боишься перегруза, но для Excel/CSV потом пригодится.

## Критерий готовности
- `docker compose up --build` поднимает инфраструктуру;
- API отвечает на `/health`;
- проект ставится через Poetry без плясок.

## Тестовые команды

```bash
poetry run uvicorn src.main:app --reload
curl http://127.0.0.1:8000/health

docker compose up --build
curl http://localhost:8000/health
```

## Что закоммитить
- каркас проекта;
- Dockerfile;
- docker-compose;
- `/health`;
- `.env.example`;
- README with startup.

## PR title
```text
feat: bootstrap project with poetry fastapi and docker compose
```

---

## Этап 2. Settings, DB session, Base, Alembic

## Цель
Подключить Postgres, async SQLAlchemy, Alembic, базовые модели и сессию.

## Ветка
```bash
git checkout -b feature/setup-db-and-alembic
```

## Что делаем
1. `Settings` через `pydantic-settings`.
2. `create_async_engine`, `async_sessionmaker`.
3. Declarative Base.
4. Alembic config под async SQLAlchemy.
5. Базовые ORM-модели: `WorkCenter`, `Batch`, `Product`.
6. Первая миграция.
7. `db ping` либо `/health/db`.

## Важные решения
- timestamps сразу через `server_default=func.now()` и `onupdate=func.now()` где нужно;
- уникальные индексы и составные индексы описать сразу;
- `shift` и `team` пока просто строки, не усложнять enum'ами, если ТЗ этого не требует жёстко.

## Критерий готовности
- миграции накатываются;
- таблицы создаются корректно;
- можно проверить соединение с БД.

## Тестовые команды

```bash
poetry run alembic revision --autogenerate -m "init models"
poetry run alembic upgrade head

docker compose exec postgres psql -U postgres -d production_control -c "\dt"
docker compose exec postgres psql -U postgres -d production_control -c "\d batches"
curl http://localhost:8000/health
```

## Что проверить руками
- есть таблицы `work_centers`, `batches`, `products`;
- у `batches` есть unique constraint на `(batch_number, batch_date)`;
- индексы реально создались.

## PR title
```text
feat: add async database setup models and alembic migrations
```

---

## Этап 3. Базовый CRUD для WorkCenter / Batch / Product

## Цель
Сделать первый реальный business slice: создавать партии, получать детали, обновлять, фильтровать, добавлять продукцию.

## Ветка
```bash
git checkout -b feature/batches-crud
```

## Что делаем
1. Pydantic schemas request/response.
2. Repository слой.
3. Service слой.
4. Endpoints:
   - `POST /api/v1/batches`
   - `GET /api/v1/batches/{batch_id}`
   - `PATCH /api/v1/batches/{batch_id}`
   - `GET /api/v1/batches`
   - `POST /api/v1/products`
5. Логика `closed_at`:
   - `is_closed=true` -> выставить `closed_at=now()` если раньше было `false`;
   - `is_closed=false` -> `closed_at=null`.
6. Автоматическое создание `WorkCenter` по `ИдентификаторРЦ`, если ещё не существует — это очень удобное решение для входного payload, чтобы API было дружелюбнее.
7. Нормальная обработка ошибок: 404, 409 duplicate batch, 422 validation.

## Важное архитектурное решение
Входящий payload сейчас на русском (`СтатусЗакрытия`, `НомерПартии`, ...). Лучше:
- на уровне Pydantic схемы поддержать **алиасы на русском**;
- внутри системы работать уже с нормальными английскими полями.

Это сразу убирает боль в коде.

## Критерий готовности
Можно:
- создать партию;
- получить по id;
- обновить;
- отфильтровать список;
- добавить продукцию.

## Тестовые команды

### Создание партии
```bash
curl -X POST http://localhost:8000/api/v1/batches \
  -H "Content-Type: application/json" \
  -d '[
    {
      "СтатусЗакрытия": false,
      "ПредставлениеЗаданияНаСмену": "Изготовить 1000 болтов М10",
      "РабочийЦентр": "Цех №1",
      "Смена": "1 смена",
      "Бригада": "Бригада Иванова",
      "НомерПартии": 22222,
      "ДатаПартии": "2024-01-30",
      "Номенклатура": "Болт М10х50",
      "КодЕКН": "EKN-12345",
      "ИдентификаторРЦ": "RC-001",
      "ДатаВремяНачалаСмены": "2024-01-30T08:00:00",
      "ДатаВремяОкончанияСмены": "2024-01-30T20:00:00"
    }
  ]'
```

### Получение партии
```bash
curl http://localhost:8000/api/v1/batches/1
```

### Обновление закрытия
```bash
curl -X PATCH http://localhost:8000/api/v1/batches/1 \
  -H "Content-Type: application/json" \
  -d '{"is_closed": true}'
```

### Фильтрация
```bash
curl "http://localhost:8000/api/v1/batches?is_closed=false&limit=20&offset=0"
```

### Добавление продукции
```bash
curl -X POST http://localhost:8000/api/v1/products \
  -H "Content-Type: application/json" \
  -d '{"unique_code": "CODE001", "batch_id": 1}'
```

## Тесты
- unit: service create/update;
- integration: create/get/list/patch batch;
- duplicate unique_code;
- duplicate `(batch_number, batch_date)`.

## PR title
```text
feat: implement work centers batches and products CRUD
```

---

## Этап 4. Синхронная агрегация продукции

## Цель
Сначала сделать простую sync-агрегацию. Не надо сразу бежать в Celery, пока нет работающей бизнес-логики.

## Ветка
```bash
git checkout -b feature/products-and-aggregation
```

## Что делаем
1. `POST /api/v1/batches/{batch_id}/aggregate`
2. На вход принимаешь список кодов либо один код — лучше сразу список, но синхронно.
3. Для каждого продукта:
   - проверка, что принадлежит партии;
   - не был агрегирован;
   - ставишь `is_aggregated=true`, `aggregated_at=now()`.
4. Возвращаешь summary:
   - total
   - aggregated
   - failed
   - errors[]

## Зачем это нужно до Celery
Потому что async task должна вызывать уже **готовую и протестированную доменную операцию**, а не содержать бизнес-логику внутри себя.

## Тестовые команды

```bash
curl -X POST http://localhost:8000/api/v1/batches/1/aggregate \
  -H "Content-Type: application/json" \
  -d '{"unique_codes": ["CODE001", "CODE002", "CODE003"]}'
```

## PR title
```text
feat: add synchronous product aggregation flow
```

---

## Этап 5. Celery + RabbitMQ + Redis backend + task status

## Цель
Внедрить асинхронный контур на уже готовую бизнес-операцию.

## Ветка
```bash
git checkout -b feature/celery-task-status
```

## Что делаем
1. Конфигурируешь `celery_app`.
2. Поднимаешь worker в compose.
3. Делаешь задачу `aggregate_products_batch`.
4. Задача внутри вызывает service-level bulk aggregation.
5. Добавляешь `update_state(state="PROGRESS", meta=...)`.
6. Endpoint:
   - `POST /api/v1/batches/{batch_id}/aggregate-async`
   - `GET /api/v1/tasks/{task_id}`

## Важный момент по архитектуре
Не пиши бизнес-логику прямо в Celery task. Правильно так:
- task = orchestration + progress + retry;
- service = доменная логика;
- repository = доступ к БД.

## Важный момент по async SQLAlchemy в Celery
Есть два варианта:
1. использовать sync SQLAlchemy отдельно для worker;
2. оставить async engine и запускать async функцию из task через helper.

Под 2 дня проще и чище сделать так:
- единая async domain/service логика;
- в Celery task запускать её через `asyncio.run(...)` в isolated helper.

Это нормально для учебно-прикладного проекта, если сделать аккуратно.

## Критерий готовности
- таска создаётся;
- worker её подхватывает;
- `GET /tasks/{task_id}` показывает статусы `PENDING/PROGRESS/SUCCESS/FAILURE`.

## Тестовые команды

### Запуск worker вручную
```bash
docker compose up -d postgres redis rabbitmq
poetry run celery -A src.app.tasks.celery_app.celery_app worker --loglevel=info
```

### Запуск async aggregation
```bash
curl -X POST http://localhost:8000/api/v1/batches/1/aggregate-async \
  -H "Content-Type: application/json" \
  -d '{"unique_codes": ["CODE001", "CODE002", "CODE003", "CODE004"]}'
```

### Проверка статуса
```bash
curl http://localhost:8000/api/v1/tasks/<TASK_ID>
```

### Проверка Flower
```bash
open http://localhost:5555
```

## Тесты
- unit на serializer статуса задачи;
- integration smoke на enqueue;
- отдельный e2e можно не писать, если не успеваешь.

## PR title
```text
feat: integrate celery worker and task status endpoints
```

---

## Этап 6. MinIO + генерация Excel отчёта

## Цель
Сделать первую файловую вертикаль: сгенерировал файл -> загрузил в MinIO -> отдал pre-signed URL.

## Ветка
```bash
git checkout -b feature/reports-minio
```

## Что делаем
1. Интеграция с MinIO.
2. Скрипт инициализации buckets.
3. `MinIOService`.
4. Celery task `generate_batch_report`.
5. Пока сначала **только Excel**, PDF оставить вторым коммитом внутри ветки или следующим PR, если времени мало.
6. Endpoint:
   - `POST /api/v1/batches/{batch_id}/reports`
7. Отчёт из 3 листов:
   - info
   - products
   - statistics

## Практическое решение
Для Excel проще всего использовать `openpyxl`. Для 2 дней это идеально.

## Критерий готовности
- отчёт генерируется;
- файл появляется в bucket `reports`;
- API возвращает URL.

## Тестовые команды

```bash
curl -X POST http://localhost:8000/api/v1/batches/1/reports \
  -H "Content-Type: application/json" \
  -d '{"format": "excel"}'

curl http://localhost:8000/api/v1/tasks/<TASK_ID>
```

### Проверка MinIO
- открыть console `http://localhost:9001`
- проверить bucket `reports`
- скачать файл по presigned URL

## PR title
```text
feat: add minio integration and excel batch report generation
```

---

## Этап 7. Импорт из Excel/CSV и экспорт партий

## Цель
Добавить file-processing pipeline с background tasks.

## Ветка
```bash
git checkout -b feature/import-export
```

## Что делаем
### Импорт
1. Upload файла через `multipart/form-data`.
2. Сохраняешь исходный файл в bucket `imports`.
3. Запускаешь task `import_batches_from_file`.
4. Task читает файл, валидирует строки, создаёт партии.
5. Возвращает summary по `created/skipped/errors`.

### Экспорт
1. Endpoint `POST /api/v1/batches/export`.
2. Фильтры -> запрос в БД -> Excel или CSV.
3. Сохраняешь в bucket `exports`.
4. Возвращаешь URL через task result.

## Практический совет
Если сроки горят:
- сначала реализуй **CSV import/export**;
- затем добавь Excel import/export.

Но если `openpyxl` уже подключён, можно сделать сразу Excel + CSV, просто через разные helper'ы.

## Тестовые команды

### Импорт
```bash
curl -X POST http://localhost:8000/api/v1/batches/import \
  -F "file=@./test_data/batches.xlsx"
```

### Экспорт
```bash
curl -X POST http://localhost:8000/api/v1/batches/export \
  -H "Content-Type: application/json" \
  -d '{
    "format": "excel",
    "filters": {
      "is_closed": false,
      "date_from": "2024-01-01",
      "date_to": "2024-01-31"
    }
  }'
```

## Тесты
- unit: row validation;
- integration: import with duplicate rows;
- export smoke.

## PR title
```text
feat: implement batch import and export background tasks
```

---

## Этап 8. Webhook subscriptions + delivery history + retry

## Цель
Добавить интеграционный контур корректно, а не “в лоб”.

## Ветка
```bash
git checkout -b feature/webhooks
```

## Что делаем
1. ORM модели:
   - `WebhookSubscription`
   - `WebhookDelivery`
2. CRUD endpoints для подписок.
3. При событиях (`batch_created`, `batch_closed`, `product_aggregated`, `report_generated`, `import_completed`) не делать прямой HTTP вызов.
4. Вместо этого:
   - находишь активные подписки на событие;
   - создаёшь записи `WebhookDelivery(status=pending)`;
   - enqueue Celery task `send_webhook_delivery`.
5. Задача отправляет webhook через `httpx`.
6. Подписываешь payload через HMAC SHA-256, например в заголовке `X-Signature`.
7. При ошибке — retries с exponential backoff.
8. Delivery history endpoint.

## Очень важное замечание
Это по сути облегчённый **transactional outbox** паттерн. Для такого проекта это правильнее, чем “после commit сразу постучаться во внешний URL”.

## Тестовые команды

### Создание подписки
```bash
curl -X POST http://localhost:8000/api/v1/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://webhook.site/your-id",
    "events": ["batch_created", "batch_closed", "product_aggregated", "report_generated"],
    "secret_key": "super-secret",
    "retry_count": 3,
    "timeout": 10
  }'
```

### История доставок
```bash
curl http://localhost:8000/api/v1/webhooks/1/deliveries
```

### Проверка подписи на стороне получателя
Проверяешь заголовок:
```text
X-Signature: sha256=<hex-digest>
```

## PR title
```text
feat: add webhook subscriptions deliveries and retry logic
```

---

## Этап 9. Redis cache + analytics endpoints

## Цель
Добавить ускорение чтения и витринную аналитику, когда CRUD уже стабилен.

## Ветка
```bash
git checkout -b feature/cache-analytics
```

## Что делаем
1. Подключаешь Redis client.
2. Делаешь тонкий cache service/decorator helper.
3. Кэшируешь:
   - dashboard stats;
   - batches list;
   - batch detail;
   - batch statistics.
4. Добавляешь invalidation в нужных местах.
5. Добавляешь endpoints:
   - `GET /api/v1/analytics/dashboard`
   - `GET /api/v1/batches/{batch_id}/statistics`
   - `POST /api/v1/analytics/compare-batches`

## Практическое замечание
Сначала можно сделать кэш **без универсального декоратора**, обычным service helper'ом. Это быстрее и меньше магии. Потом уже рефакторить.

## Тестовые команды

```bash
curl http://localhost:8000/api/v1/analytics/dashboard
curl http://localhost:8000/api/v1/batches/1/statistics
curl -X POST http://localhost:8000/api/v1/analytics/compare-batches \
  -H "Content-Type: application/json" \
  -d '{"batch_ids": [1,2,3]}'
```

### Проверка Redis keys
```bash
docker compose exec redis redis-cli
KEYS *
GET dashboard_stats
```

## PR title
```text
feat: add redis caching and analytics endpoints
```

---

## Этап 10. Celery Beat scheduled tasks

## Цель
Закрыть фоновые операционные процессы.

## Ветка
```bash
git checkout -b feature/scheduled-tasks
```

## Что делаем
1. `auto_close_expired_batches`
2. `cleanup_old_files`
3. `update_cached_statistics`
4. `retry_failed_webhooks`
5. Celery Beat config
6. Поднять отдельный `celery_beat` service в compose

## Тестовые команды

### Проверка закрытия просроченных партий
```bash
poetry run celery -A src.app.tasks.celery_app.celery_app call src.app.tasks.scheduler.auto_close_expired_batches
```

### Проверка cleanup
```bash
poetry run celery -A src.app.tasks.celery_app.celery_app call src.app.tasks.scheduler.cleanup_old_files
```

### Проверка schedule
```bash
docker compose logs -f celery_beat
```

## PR title
```text
feat: add scheduled celery beat tasks for maintenance jobs
```

# 16. Definition of Done для всего проекта

Проект можно считать вменяемо завершённым, если:
- поднимается через `docker compose up --build`;
- миграции проходят;
- CRUD по партиям и продукции работает;
- есть sync и async aggregation;
- есть task status endpoint;
- генерируется хотя бы Excel report и сохраняется в MinIO;
- работает import/export хотя бы в одном формате стабильно;
- webhook subscriptions и delivery history реализованы;
- есть retry delivery;
- dashboard analytics работает;
- есть Redis cache с invalidation;
- есть Celery Beat с базовыми maintenance jobs;
- есть README и команды для локальной проверки;
- есть минимум smoke + integration + unit tests на ключевые use cases.
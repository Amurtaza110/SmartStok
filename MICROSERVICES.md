# SmartStock service architecture

SmartStock runs as two application services:

- **Inventory service** (`inventory`): the Django UI, authentication, inventory and sales domain, and the sole owner of the operational SQLite database.
- **AI service** (`ai`): an independent FastAPI service for live-context chat, semantic product search, and demand forecasts. It owns chat history and forecast caches in its own SQLite database volume and has no direct access to the inventory database.

Django is the browser-facing gateway. It calls the AI service with `AI_SERVICE_TOKEN`; the AI service reads live inventory data through token-protected endpoints owned by Django. `INVENTORY_SERVICE_TOKEN` protects those endpoints. Do not expose the internal AI endpoints publicly or reuse these credentials for user authentication.

## Run with Docker Compose

Create a local `.env` from `.env.example` and set unique random values for `SECRET_KEY`, `AI_SERVICE_TOKEN`, and `INVENTORY_SERVICE_TOKEN`. Then run:

```powershell
docker compose up --build
```

The application is available at `http://localhost:8000`. Compose persists inventory records in `sqlite_data`, uploaded images in `media_data`, and AI chat/forecast state in `ai_data`. Ollama runs separately; configure `OLLAMA_BASE_URL` and install the model named by `OLLAMA_MODEL` to enable chat.

## Service contracts

- `GET /health/` — inventory process health check.
- `GET /internal/ai/context/` — live operational context for chat.
- `GET /internal/ai/products/` — active product text for search.
- `GET /internal/ai/sales/{product_id}/?days=120` — daily completed sales for forecasts.
- AI service `GET /health`, `POST /v1/chat`, `GET /v1/search`, `POST /v1/reindex`, and `GET /v1/forecast/{product_id}`.
- AI-owned state APIs include chat history/clear and forecast list/batch operations. Legacy data can be imported with `python manage.py migrate_ai_data`.

Internal inventory endpoints require `X-Service-Token`; Django-to-AI calls require the same header with the independent AI token. Forecasts are derived from recorded sales only. Products without sales history receive an explicit insufficient-data response rather than generated sample values.

## SQLite data and backups

The Django inventory database remains a SQLite file on the `sqlite_data` Docker volume. Back up that volume to preserve inventory data. Run `python manage.py migrate_ai_data` while the AI service is available to transfer legacy chat and forecast records. The import is idempotent. The former demo seeder has been removed.

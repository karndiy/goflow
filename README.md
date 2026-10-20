# GoFlow

Internal social media management tool (Facebook Pages and TikTok first),
built as a modular monolith with a FastAPI backend. See `Claude.md` for
the full project guide, architecture rules, and milestone plan.

## Status

Milestone 1 (runnable foundation) is implemented: FastAPI app, async
SQLAlchemy database session, Redis connectivity, Alembic migrations, and
a health endpoint.

## Local development

1. Copy `.env.example` to `.env` and adjust values as needed.
2. Start PostgreSQL and Redis:

   ```
   docker compose up -d db redis
   ```

3. Create a virtual environment and install dependencies:

   ```
   python -m venv .venv
   .venv/Scripts/activate   # Windows
   pip install -e ".[dev]"
   ```

4. Apply database migrations:

   ```
   alembic upgrade head
   ```

5. Run the API:

   ```
   uvicorn app.main:app --reload
   ```

6. Check health:

   ```
   curl http://localhost:8000/api/v1/health
   ```

## Running the full stack with Docker Compose

```
docker compose up --build
```

## Tests

```
pytest
ruff check .
ruff format --check .
mypy app
```

Integration tests require PostgreSQL and Redis to be reachable (see
`DATABASE_URL` / `REDIS_URL` in `.env`).

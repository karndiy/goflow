# GoFlow

Internal social media management tool (Facebook Pages and TikTok first),
built as a modular monolith with a FastAPI backend. See `Claude.md` for
the full project guide, architecture rules, and milestone plan.

## Status

Milestones 1-4 are implemented (foundation, auth/workspaces, mock
connector + scheduler/worker, Facebook connector), plus a React
dashboard (content studio, publishing queue, calendar, accounts) ahead
of the full Milestone 6 scope.

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

This starts the API, PostgreSQL, Redis, scheduler, and worker. Create
the first admin account with:

```
python scripts/create_admin.py --email you@example.com --password "..." --workspace-name "My Workspace"
```

## Frontend dashboard

The dashboard (`frontend/`) is a separate React + Vite + TypeScript app,
not yet containerized — run it alongside the backend:

```
cd frontend
npm install
npm run dev
```

It serves on `http://localhost:3000` (matching `FRONTEND_BASE_URL`) and
talks to the API at `VITE_API_BASE_URL` (see `frontend/.env.development`).
Sign in with the admin account created above.

## Tests

```
pytest
ruff check .
ruff format --check .
mypy app
```

Integration tests require PostgreSQL and Redis to be reachable (see
`DATABASE_URL` / `REDIS_URL` in `.env`).

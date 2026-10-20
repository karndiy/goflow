# GoFlow --- Claude CLI Project Guide

> **Purpose:** This file is the source of project-level instructions for
> Claude Code / Claude CLI. Read it before making changes.
>
> **Project:** GoFlow --- an internal Social Media Management Tool,
> starting with Facebook and TikTok, designed to add other platforms
> through independent connectors.

## 1. Project decisions

-   **Deployment:** Internal Tool, initially used by one user.
-   **Backend:** Python + FastAPI.
-   **MVP platforms:** Facebook Pages and TikTok, including scheduled
    publishing.
-   **Architecture:** Modular Monolith + background scheduler/worker +
    Social Connector architecture.
-   **Database:** PostgreSQL.
-   **ORM / migrations:** SQLAlchemy 2.x / Alembic.
-   **Queue:** Redis + RQ.
-   **HTTP client:** HTTPX.
-   **Validation:** Pydantic v2.
-   **Testing:** pytest.
-   **Local development:** Docker Compose.
-   **Initial UI:** Web dashboard, content studio, publishing queue,
    account management, and calendar. Keep UI work secondary until core
    API, data model, and scheduling are reliable.
-   **Future direction:** Support multiple users/workspaces and
    additional platforms without rewriting core publishing logic.

Do not silently change these decisions. If a change is necessary,
explain why and keep the implementation consistent.

## 2. Product goals

GoFlow should let the operator:

1.  Connect authorized Facebook Pages and TikTok accounts through
    official OAuth flows.
2.  Create and edit drafts.
3.  Upload and manage media.
4.  Create platform-specific content variants.
5.  Select one or more social accounts as targets.
6.  Schedule publishing for a specific date and time.
7.  Publish in background processes even when the browser is closed.
8.  View publishing status, errors, and attempt history.
9.  Retry eligible failures safely.
10. Add future platforms by implementing a connector, not by rewriting
    scheduling or content modules.

### MVP boundaries

-   Start with a single operator but implement `users`, `workspaces`,
    and `workspace_members` so multi-user support can be added later.
-   Start with Facebook Pages, not personal Facebook profile publishing.
-   Use only official platform APIs and permitted scopes.
-   Do not claim a post is published merely because an API request was
    accepted. Some APIs return a processing identifier and require
    status polling.
-   Do not bypass app review, API permissions, platform privacy
    settings, or platform restrictions.
-   Analytics should only expose metrics actually returned by the
    relevant official API and authorized scopes.
-   If a platform capability is not approved or available, surface a
    clear status/message and keep the rest of the app usable.

## 3. Architecture rules

Use a **modular monolith**. Keep business logic separate from transport,
database access, and platform-specific API calls.

Main responsibilities:

-   `app/modules/content`: content drafts, platform variants, media
    references.
-   `app/modules/accounts`: connected accounts and account lifecycle.
-   `app/modules/publishing`: scheduling, job claiming, retries, status
    transitions, reconciliation.
-   `app/connectors`: platform-specific API implementation behind a
    shared interface.
-   `app/tasks`: queue integration and background task entry points.
-   `app/core`: configuration, database session, security, token
    encryption, logging.
-   `app/api`: top-level API router and shared dependencies.

Never call Meta or TikTok APIs directly from content routes or generic
business logic. All platform API calls must go through the relevant
connector/client.

Do not create microservices for the MVP. Keep API, scheduler, and worker
as separate processes/containers built from the same application image.

## 4. Suggested repository structure

Use this structure as the target. If the repository already has a valid
structure, inspect it first and adapt incrementally rather than
overwriting work.

``` text
goflow/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   ├── encryption.py
│   │   └── logging.py
│   ├── api/
│   │   ├── router.py
│   │   └── dependencies.py
│   ├── modules/
│   │   ├── auth/
│   │   ├── accounts/
│   │   ├── content/
│   │   ├── publishing/
│   │   └── analytics/
│   ├── connectors/
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── common.py
│   │   ├── facebook/
│   │   │   ├── connector.py
│   │   │   ├── oauth.py
│   │   │   └── client.py
│   │   └── tiktok/
│   │       ├── connector.py
│   │       ├── oauth.py
│   │       ├── client.py
│   │       └── media.py
│   ├── tasks/
│   │   ├── queue.py
│   │   └── jobs.py
│   └── schemas/
│       ├── common.py
│       └── errors.py
├── alembic/
│   └── versions/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── contract/
├── storage/
│   └── .gitkeep
├── scripts/
│   └── create_admin.py
├── .env.example
├── .gitignore
├── alembic.ini
├── Dockerfile
├── compose.yaml
├── pyproject.toml
└── README.md
```

## 5. Code quality and implementation conventions

-   Use Python type hints for public functions and service boundaries.
-   Use `async def` for FastAPI routes and async I/O. Keep
    database/session usage consistent; do not mix sync and async
    SQLAlchemy styles casually.
-   Prefer small service functions and explicit dependency injection.
-   Keep Pydantic request/response schemas separate from SQLAlchemy
    models.
-   Use SQLAlchemy 2.x declarative mappings and explicit transactions.
-   Use Alembic migrations for every schema change. Do not rely on
    `create_all()` in production.
-   Use timezone-aware datetimes. Store timestamps as PostgreSQL
    `TIMESTAMPTZ`; normalize scheduled times to UTC and display them in
    the workspace timezone (`Asia/Bangkok` by default).
-   Use UUID primary keys for core records.
-   Return consistent API errors; never expose secrets, tokens, stack
    traces, or raw provider responses containing sensitive data.
-   Add tests with every feature and bug fix.
-   Keep external API calls behind HTTP clients that can be mocked in
    tests.
-   Use configuration from environment variables; do not hardcode
    secrets, account IDs, access tokens, or API versions.
-   Avoid unnecessary abstractions and dependencies. Add a dependency
    only when it solves a concrete need.
-   Before editing, inspect the current files and preserve existing
    work. Do not overwrite files blindly.

## 6. Connector contract

All platform connectors must implement a shared contract similar to:

``` python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

PublishStatus = Literal["published", "processing", "failed", "unknown"]

@dataclass
class PublishRequest:
    account_id: str
    text: str
    media_type: Literal["none", "image", "video", "carousel"]
    media_urls: list[str]
    options: dict[str, Any]

@dataclass
class PublishResult:
    status: PublishStatus
    external_post_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw_response: dict[str, Any] | None = None

class SocialConnector(ABC):
    platform: str

    @abstractmethod
    async def publish(self, request: PublishRequest) -> PublishResult:
        ...

    @abstractmethod
    async def get_publish_status(self, external_post_id: str) -> PublishResult:
        ...

    @abstractmethod
    async def validate_account(self, account_id: str) -> bool:
        ...
```

This is a contract, not a claim that all platforms behave identically.
Add platform-specific capabilities and validation where needed. Avoid
forcing unsupported media types or operations through a generic API. If
useful, add a capability declaration such as `supported_media_types`,
`supports_direct_publish`, and `supports_status_polling`.

`ConnectorRegistry` should register connector instances once during
application/worker startup and retrieve them by normalized platform
name. Duplicate registrations should fail fast. Unsupported platforms
should return a controlled application error.

### Connector-specific requirements

**Facebook** - Target Facebook Pages authorized by the user; do not
implement publishing to personal profiles. - Use the official Meta Graph
API and scopes required for the exact endpoints. - Store Page ID,
display name, and the appropriate token securely. - Handle token
expiry/revocation, API version configuration, rate limits, permission
errors, and provider error payloads. - Treat media publishing as
endpoint-specific; implement text/image first and add video only after
verifying the current official API flow.

**TikTok** - Use official TikTok Login Kit and Content Posting API. -
Verify Creator Info and relevant constraints before posting where
required. - Implement the API's supported direct-post or upload/draft
flow based on approved scopes and app status. - Save the returned
publish identifier and poll status where required. - Do not mark a post
`published` merely because the initial request was accepted. - Respect
privacy options, audit/review restrictions, domain verification
requirements for URL-based media pulls, and current platform policy.

Official docs to consult during implementation: - Meta Graph API:
https://developers.facebook.com/docs/graph-api/ - Meta Pages API:
https://developers.facebook.com/docs/pages-api/ - TikTok Content Posting
API:
https://developers.tiktok.com/docs/en/content-posting-api-get-started

Platform APIs and permission requirements can change. Verify current
official documentation before implementing or claiming a capability.

## 7. Database model plan

Implement these tables incrementally with SQLAlchemy models and Alembic
migrations:

-   `users`: `id`, `email`, `password_hash`, `is_active`, timestamps.
-   `workspaces`: `id`, `name`, `timezone`, timestamps.
-   `workspace_members`: `workspace_id`, `user_id`, `role`; roles
    initially `owner`, `admin`, `editor`, `viewer`.
-   `social_accounts`: `id`, `workspace_id`, `platform`,
    `external_account_id`, `account_name`, `status`, timestamps; unique
    constraint on `(workspace_id, platform, external_account_id)`.
-   `oauth_tokens`: `social_account_id`, encrypted access token,
    encrypted refresh token if supported, expiry, updated timestamp.
-   `contents`: `id`, `workspace_id`, `title`, `status`, timestamps.
-   `content_variants`: `id`, `content_id`, `platform`, `text`,
    `media_type`, `payload_json`; unique `(content_id, platform)`.
-   `media_assets`: `id`, `workspace_id`, `storage_key`, `mime_type`,
    `size_bytes`, metadata, timestamps.
-   `content_variant_media`: join table if variants can reference
    multiple assets.
-   `publishing_jobs`: `id`, `content_variant_id`, `social_account_id`,
    `scheduled_at`, `status`, `external_post_id`, `idempotency_key`,
    attempts, last error, timestamps.
-   `publish_attempts`: `id`, `job_id`, `attempt_number`, status,
    provider request ID, sanitized result, error code/message,
    timestamps; unique `(job_id, attempt_number)`.
-   `post_analytics`: account/post identifiers, metric name/value,
    collection time.
-   `audit_logs`: actor, workspace, action, target, sanitized metadata,
    timestamp.
-   OAuth state records or equivalent server-side state storage with
    expiry and one-time use.

Use foreign keys, indexes for due jobs and account lookups, and explicit
delete behavior. Avoid storing tokens or sensitive data in general JSON
fields. Do not log token values.

## 8. Publishing job lifecycle

Use a controlled state machine. Suggested job statuses:

-   `scheduled`
-   `queued`
-   `publishing`
-   `processing`
-   `published`
-   `failed`
-   `cancelled`
-   `unknown`

Important behavior:

1.  Scheduler scans PostgreSQL for due jobs.
2.  Claim due jobs atomically inside a transaction, using an approach
    such as `SELECT ... FOR UPDATE SKIP LOCKED` or an equivalent atomic
    claim.
3.  Change state to `queued` before enqueuing to Redis.
4.  If enqueue fails, provide a recovery scan for queued jobs that were
    not actually delivered to a worker.
5.  Worker loads the job, account, token, and platform variant;
    validates permissions and content.
6.  Create a `publish_attempts` record for each attempt.
7.  Call the connector and persist the result.
8.  For asynchronous platform processing, store the remote identifier
    and set `processing`; poll status in a later job.
9.  Retry only errors that are safe and eligible for retry, respecting
    provider rate limits and `Retry-After`.
10. If a request times out after it may have reached the provider, set
    `unknown` and reconcile remote status before retrying. Do not
    blindly resend.
11. Make cancellation safe: only cancel jobs that have not entered a
    non-cancellable publishing stage, and communicate this clearly.
12. Recompute parent content status from all target jobs (`published`,
    `partial_failure`, `failed`, etc.).

Redis/RQ is a delivery mechanism, not the source of truth. PostgreSQL
remains authoritative.

## 9. API design

Use prefix `/api/v1`. Keep route handlers thin and move logic into
services.

### Auth / workspace

-   `POST /api/v1/auth/login`
-   `POST /api/v1/auth/logout`
-   `GET /api/v1/auth/me`
-   `GET /api/v1/workspace`
-   `PATCH /api/v1/workspace`

### Accounts / OAuth

-   `GET /api/v1/accounts`
-   `POST /api/v1/accounts/facebook/connect`
-   `GET /api/v1/oauth/facebook/callback`
-   `POST /api/v1/accounts/tiktok/connect`
-   `GET /api/v1/oauth/tiktok/callback`
-   `POST /api/v1/accounts/{id}/refresh`
-   `DELETE /api/v1/accounts/{id}`

### Media / content

-   `POST /api/v1/media`
-   `GET /api/v1/media`
-   `POST /api/v1/contents`
-   `GET /api/v1/contents`
-   `GET /api/v1/contents/{id}`
-   `PATCH /api/v1/contents/{id}`
-   `DELETE /api/v1/contents/{id}`
-   `POST /api/v1/contents/{id}/schedule`
-   `POST /api/v1/contents/{id}/publish-now`
-   `POST /api/v1/contents/{id}/cancel`

### Publishing / calendar / analytics

-   `GET /api/v1/publishing/jobs`
-   `GET /api/v1/publishing/jobs/{id}`
-   `POST /api/v1/publishing/jobs/{id}/retry`
-   `GET /api/v1/publishing/calendar`
-   `GET /api/v1/analytics/overview`
-   `GET /api/v1/health`

For all endpoints: - Validate workspace ownership and permissions
server-side. - Use pagination for lists. - Validate platform
capabilities and account status before scheduling. - Do not trust
`platform` or `workspace_id` supplied by a client without checking
database ownership and authorization. - Use explicit Pydantic request
and response models. - Never return encrypted token fields. - Document
response codes and errors in OpenAPI.

## 10. OAuth and secrets

-   Use OAuth `state` generated with a cryptographically secure random
    source, bound to the initiating user/session, expiry-limited, and
    one-time use.
-   Validate callback state before exchanging authorization codes.
-   Perform code exchange server-side over HTTPS.
-   Encrypt access and refresh tokens at rest with a dedicated
    encryption key.
-   Keep encryption keys separate from app/session signing secrets.
-   Never commit `.env` or credentials.
-   Provide `.env.example` with empty values/placeholders only.
-   Mask credentials in logs and error messages.
-   Implement reconnect/revocation states and account health checks.
-   Use HTTPS and secure cookies in production; localhost development
    may use relaxed cookie settings only when explicitly configured.

Suggested environment variables: - `APP_ENV` - `APP_SECRET_KEY` -
`DATABASE_URL` - `REDIS_URL` - `APP_BASE_URL` - `FRONTEND_BASE_URL` -
`TOKEN_ENCRYPTION_KEY` - `META_APP_ID` - `META_APP_SECRET` -
`META_GRAPH_API_VERSION` - `TIKTOK_CLIENT_KEY` -
`TIKTOK_CLIENT_SECRET` - `SESSION_COOKIE_SECURE` - `LOG_LEVEL`

Do not invent credentials or imply external API access is configured
when it is not.

## 11. Testing requirements

Write tests before declaring features complete.

-   Unit tests for services, state transitions, registry, validation,
    and retry classification.
-   Connector contract tests using mocked HTTP responses.
-   Integration tests against a disposable PostgreSQL/Redis environment
    where practical.
-   OAuth tests for invalid/missing/reused/expired `state`.
-   Scheduler tests for due-time handling, timezone conversion, atomic
    claiming, and duplicate enqueue recovery.
-   Worker tests for success, processing, permanent errors, transient
    errors, and uncertain timeout.
-   Authorization tests proving a user cannot read or modify another
    workspace's records.
-   Never publish to real social accounts in the default test suite.
-   Live API smoke tests must be explicit opt-in and require configured
    credentials.

Run at minimum: - `pytest` - `ruff check .` - `ruff format --check .` -
`mypy app` if mypy is configured

If a tool is not yet installed/configured, add it deliberately to
`pyproject.toml` or document why it is deferred. Do not claim tests
passed unless they were run and passed.

## 12. Development workflow for Claude CLI

At the beginning of a task:

1.  Read this file and `README.md`.
2.  Inspect the repository status and current files before editing.
3.  Identify the smallest coherent implementation slice.
4.  State the files to change and acceptance criteria briefly.
5.  Implement the change, including tests and migrations if applicable.
6.  Run relevant tests, lint, and type checks.
7.  Review `git diff` for accidental changes and secrets.
8.  Summarize what changed, commands run, results, and any manual setup
    still required.

Do not: - Rewrite the project wholesale without a request. - Replace
existing user work just to match the suggested structure. - create
placeholder code that reports fake successful publishing. - use
unofficial APIs, browser automation, or scraping to bypass official
platform access restrictions. - mark asynchronous publish requests as
successful before confirmation. - silently swallow exceptions or leave
TODOs for critical security/reliability behavior. - introduce a new
database or queue technology without explaining the reason.

If requirements are ambiguous, choose the smallest safe implementation
that preserves the architecture and document the assumption. Ask a
concise question only if a decision blocks implementation.

## 13. Recommended implementation milestones

### Milestone 1 --- Runnable foundation

-   Create `pyproject.toml`, `Dockerfile`, `compose.yaml`,
    configuration, FastAPI app, database session, and health route.
-   Start PostgreSQL and Redis.
-   Add Alembic and an initial migration.
-   Add tests for health and database connectivity.

**Acceptance:** API starts locally and `GET /api/v1/health` works;
migrations apply cleanly.

### Milestone 2 --- Authentication and data model

-   Add users, workspaces, membership, and single-admin bootstrap
    script.
-   Implement authentication and workspace-scoped dependencies.
-   Add social account, token, content, media, job, and attempt models.
-   Add migrations and authorization tests.

**Acceptance:** authenticated user can create/read drafts; unauthorized
cross-workspace access is denied.

### Milestone 3 --- Mock connector and scheduling

-   Implement base connector, registry, and a mock connector.
-   Add queue, scheduler, worker, state transitions, attempts, recovery,
    and reconciliation interfaces.
-   Prove scheduling works without real provider credentials.

**Acceptance:** a due mock job is processed once and status/attempts are
persisted.

### Milestone 4 --- Facebook

-   Implement OAuth, account discovery, token encryption, and supported
    publishing operations.
-   Add provider error mapping and tests with mocked HTTP responses.
-   Test real publishing only when explicitly enabled and configured.

**Acceptance:** an authorized Facebook Page can publish supported
content and the resulting status is persisted accurately.

### Milestone 5 --- TikTok

-   Implement OAuth, required scopes, Creator Info checks, media
    workflow, direct-post/draft behavior, and publish-status polling
    according to approved access.
-   Add mock-based contract tests.
-   Document developer-console setup and app review constraints.

**Acceptance:** the supported flow works with an authorized/test
account; if platform approval is pending, mock tests pass and the
blocker is documented honestly.

### Milestone 6 --- UI and operational readiness

-   Add dashboard, content editor, account page, publishing queue, and
    calendar.
-   Add logs, backup/restore instructions, health checks, and deployment
    documentation.
-   Test recovery from API/worker restart.

**Acceptance:** the operator can create, schedule, monitor, and
troubleshoot posts through the UI.

## 14. Definition of done

A feature is done only when: - Code follows the project architecture and
typing conventions. - Relevant tests are added and pass. - Migrations
are included for schema changes. - Errors are handled without exposing
secrets. - Documentation/configuration examples are updated. - No real
social post is sent by automated tests. - The final report accurately
states what was implemented, tested, and left pending.

------------------------------------------------------------------------

**First task for Claude Code:** inspect the existing repository. If it
is empty, implement Milestone 1 only: a runnable FastAPI foundation with
configuration, PostgreSQL/SQLAlchemy setup, Redis configuration, Docker
Compose, Alembic initialization, `/api/v1/health`, and tests. Do not
implement real Facebook or TikTok publishing until the foundation and
mock-based workflow are in place.

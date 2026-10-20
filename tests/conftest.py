import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

import httpx
import pytest_asyncio

from app.core.database import AsyncSessionLocal, engine
from app.core.redis import redis_client
from app.core.security import hash_password
from app.main import app
from app.modules.auth.models import User, Workspace, WorkspaceMember


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _dispose_connections_after_tests():
    yield
    await engine.dispose()
    await redis_client.aclose()


@pytest_asyncio.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def user_factory(db_session):
    created: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def _create(
        password: str = "correct horse battery staple",
        role: str = "owner",
        workspace_name: str = "Test Workspace",
    ) -> SimpleNamespace:
        email = f"test-{uuid.uuid4().hex}@example.com"
        user = User(email=email, password_hash=hash_password(password))
        workspace = Workspace(name=workspace_name, timezone="Asia/Bangkok")
        db_session.add_all([user, workspace])
        await db_session.flush()

        membership = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role)
        db_session.add(membership)
        await db_session.commit()

        created.append((user.id, workspace.id))
        return SimpleNamespace(user=user, workspace=workspace, email=email, password=password)

    yield _create

    for user_id, workspace_id in created:
        workspace = await db_session.get(Workspace, workspace_id)
        if workspace is not None:
            await db_session.delete(workspace)
        user = await db_session.get(User, user_id)
        if user is not None:
            await db_session.delete(user)
    await db_session.commit()

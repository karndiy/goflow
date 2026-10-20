import uuid

from sqlalchemy import select

from app.core.security import verify_password
from app.modules.auth.models import User, Workspace, WorkspaceMember
from scripts.create_admin import create_admin


async def test_create_admin_creates_user_workspace_and_owner_membership(db_session):
    email = f"admin-{uuid.uuid4().hex}@example.com"

    try:
        await create_admin(email, "super-secret", "Bootstrap Workspace", "Asia/Bangkok")

        user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
        assert verify_password("super-secret", user.password_hash)

        membership = (
            await db_session.execute(
                select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
            )
        ).scalar_one()
        assert membership.role == "owner"

        workspace = await db_session.get(Workspace, membership.workspace_id)
        assert workspace.name == "Bootstrap Workspace"
    finally:
        user = (
            await db_session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is not None:
            membership = (
                await db_session.execute(
                    select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
                )
            ).scalar_one_or_none()
            if membership is not None:
                workspace = await db_session.get(Workspace, membership.workspace_id)
                if workspace is not None:
                    await db_session.delete(workspace)
            await db_session.delete(user)
            await db_session.commit()


async def test_create_admin_is_idempotent_for_existing_email(user_factory, capsys):
    identity = await user_factory()

    await create_admin(identity.email, "irrelevant", "Irrelevant Workspace", "UTC")

    captured = capsys.readouterr()
    assert "already exists" in captured.out

"""Bootstrap the first admin user and workspace for a fresh GoFlow database."""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.modules.auth.models import User, Workspace, WorkspaceMember  # noqa: E402


async def create_admin(email: str, password: str, workspace_name: str, timezone: str) -> None:
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing is not None:
            print(f"User {email} already exists; nothing to do.")
            return

        user = User(email=email, password_hash=hash_password(password))
        workspace = Workspace(name=workspace_name, timezone=timezone)
        db.add_all([user, workspace])
        await db.flush()

        membership = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
        db.add(membership)
        await db.commit()

        print(f"Created user {email} as owner of workspace '{workspace_name}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--workspace-name", default="Default Workspace")
    parser.add_argument("--timezone", default="Asia/Bangkok")
    args = parser.parse_args()

    asyncio.run(create_admin(args.email, args.password, args.workspace_name, args.timezone))


if __name__ == "__main__":
    main()

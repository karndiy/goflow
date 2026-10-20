from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_membership
from app.core.database import get_db
from app.modules.accounts import service
from app.modules.accounts.schemas import SocialAccountRead
from app.modules.auth.models import WorkspaceMember

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[SocialAccountRead])
async def list_accounts(
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_social_accounts(db, membership.workspace_id)

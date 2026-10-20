from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_membership
from app.core.database import get_db
from app.modules.accounts.models import SocialAccount
from app.modules.auth.models import WorkspaceMember
from app.modules.content.models import Content, ContentVariant
from app.modules.publishing.models import PublishingJob

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary")
async def dashboard_summary(
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> dict:
    content_rows = await db.execute(
        select(Content.status, func.count())
        .where(Content.workspace_id == membership.workspace_id)
        .group_by(Content.status)
    )
    content_by_status = {status: count for status, count in content_rows.all()}

    job_rows = await db.execute(
        select(PublishingJob.status, func.count())
        .select_from(PublishingJob)
        .join(ContentVariant, PublishingJob.content_variant_id == ContentVariant.id)
        .join(Content, ContentVariant.content_id == Content.id)
        .where(Content.workspace_id == membership.workspace_id)
        .group_by(PublishingJob.status)
    )
    jobs_by_status = {status: count for status, count in job_rows.all()}

    account_rows = await db.execute(
        select(SocialAccount.platform, SocialAccount.status, func.count())
        .where(SocialAccount.workspace_id == membership.workspace_id)
        .group_by(SocialAccount.platform, SocialAccount.status)
    )
    accounts = [
        {"platform": platform, "status": acct_status, "count": count}
        for platform, acct_status, count in account_rows.all()
    ]

    return {
        "content_by_status": content_by_status,
        "jobs_by_status": jobs_by_status,
        "accounts": accounts,
    }

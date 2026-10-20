import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import anthropic
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_token, encrypt_token
from app.modules.assistant.models import AISettings, UserRequest
from app.modules.auth.models import User

MAX_RESPONSE_TOKENS = 8192


@dataclass
class ClaudeCallResult:
    succeeded: bool
    text: str | None = None
    error_message: str | None = None


async def call_claude(
    ai_settings: AISettings,
    user_message: str,
    system: str | None = None,
    max_tokens: int = MAX_RESPONSE_TOKENS,
) -> ClaudeCallResult:
    """Shared Claude call used by both the Requests feature and content generation."""
    api_key = decrypt_token(ai_settings.encrypted_api_key)

    try:
        async with anthropic.AsyncAnthropic(api_key=api_key) as client:
            create_kwargs: dict[str, Any] = {
                "model": ai_settings.model,
                "max_tokens": max_tokens,
                "output_config": {"effort": "medium"},
                "messages": [{"role": "user", "content": user_message}],
            }
            if system is not None:
                create_kwargs["system"] = system
            response = await client.messages.create(**create_kwargs)
    except anthropic.AuthenticationError:
        return ClaudeCallResult(succeeded=False, error_message="Invalid Anthropic API key")
    except anthropic.PermissionDeniedError:
        return ClaudeCallResult(
            succeeded=False, error_message="Anthropic API key lacks permission for this model"
        )
    except anthropic.NotFoundError:
        return ClaudeCallResult(
            succeeded=False, error_message=f"Unknown model '{ai_settings.model}'"
        )
    except anthropic.RateLimitError:
        return ClaudeCallResult(
            succeeded=False, error_message="Rate limited by Anthropic API, try again later"
        )
    except anthropic.APIConnectionError:
        return ClaudeCallResult(succeeded=False, error_message="Could not reach the Anthropic API")
    except anthropic.APIStatusError as exc:
        return ClaudeCallResult(
            succeeded=False, error_message=f"Anthropic API error: {exc.message}"
        )

    if response.stop_reason == "refusal":
        return ClaudeCallResult(succeeded=False, error_message="Claude declined this request")

    text = "".join(block.text for block in response.content if block.type == "text")
    return ClaudeCallResult(succeeded=True, text=text)


async def get_ai_settings(db: AsyncSession, workspace_id: uuid.UUID) -> AISettings | None:
    result = await db.execute(select(AISettings).where(AISettings.workspace_id == workspace_id))
    return result.scalar_one_or_none()


async def upsert_ai_settings(
    db: AsyncSession, workspace_id: uuid.UUID, api_key: str, model: str
) -> AISettings:
    settings = await get_ai_settings(db, workspace_id)
    encrypted = encrypt_token(api_key)
    if settings is None:
        settings = AISettings(workspace_id=workspace_id, encrypted_api_key=encrypted, model=model)
        db.add(settings)
    else:
        settings.encrypted_api_key = encrypted
        settings.model = model
    await db.commit()
    await db.refresh(settings)
    return settings


async def create_request(
    db: AsyncSession, workspace_id: uuid.UUID, requester: User, prompt: str
) -> UserRequest:
    request = UserRequest(
        workspace_id=workspace_id,
        requester_user_id=requester.id,
        requester_email=requester.email,
        prompt=prompt,
        status="pending",
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request


async def answer_request(db: AsyncSession, request: UserRequest, ai_settings: AISettings) -> None:
    result = await call_claude(ai_settings, request.prompt)

    if result.succeeded:
        request.response = result.text
        request.status = "answered"
        request.answered_at = datetime.now(UTC)
    else:
        request.status = "failed"
        request.error_message = result.error_message

    await db.commit()


async def list_requests(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    limit: int,
    offset: int,
    search: str | None = None,
) -> tuple[list[UserRequest], int]:
    filters = [UserRequest.workspace_id == workspace_id]
    if search:
        pattern = f"%{search}%"
        filters.append(
            or_(UserRequest.prompt.ilike(pattern), UserRequest.requester_email.ilike(pattern))
        )

    total = (
        await db.execute(select(func.count()).select_from(UserRequest).where(*filters))
    ).scalar_one()

    result = await db.execute(
        select(UserRequest)
        .where(*filters)
        .order_by(UserRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def get_request(
    db: AsyncSession, workspace_id: uuid.UUID, request_id: uuid.UUID
) -> UserRequest | None:
    result = await db.execute(
        select(UserRequest).where(
            UserRequest.id == request_id, UserRequest.workspace_id == workspace_id
        )
    )
    return result.scalar_one_or_none()

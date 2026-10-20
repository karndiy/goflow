from fastapi import APIRouter

from app.api.health import router as health_router
from app.modules.accounts.router import router as accounts_router
from app.modules.auth.router import router as auth_router
from app.modules.content.router import router as content_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(content_router)
api_router.include_router(accounts_router)

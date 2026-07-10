from fastapi import APIRouter

from app.api.repos import router as repos_router
from app.api.routes import router as legacy_router

router = APIRouter()
router.include_router(legacy_router)
router.include_router(repos_router)

__all__ = ["router"]

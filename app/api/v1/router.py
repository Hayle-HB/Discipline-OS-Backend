from fastapi import APIRouter

from app.api.v1 import analytics, auth, routines, tasks

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(routines.router, prefix="/routines", tags=["routines"])

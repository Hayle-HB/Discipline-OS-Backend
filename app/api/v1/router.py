from fastapi import APIRouter

from app.api.v1 import analytics, auth, goals, routines, shares, tasks

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(goals.router, prefix="/goals", tags=["goals"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(routines.router, prefix="/routines", tags=["routines"])
api_router.include_router(shares.router, prefix="/shares", tags=["shares"])

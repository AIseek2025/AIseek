from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, posts, social, messages, search, interaction, upload, observability, media
from app.api.v1.endpoints import ai_jobs
from app.api.v1.endpoints import ops
from app.api.v1.endpoints import feed

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(feed.router, prefix="/posts", tags=["posts"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(social.router, prefix="/social", tags=["social"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(interaction.router, prefix="/interaction", tags=["interaction"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(observability.router, prefix="/observability", tags=["observability"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(ai_jobs.router, prefix="/ai", tags=["ai"])
api_router.include_router(ops.router, prefix="/ops", tags=["ops"])
from app.api.v1.endpoints.ai_creation import routes as ai_routes
api_router.include_router(ai_routes.router, prefix="/ai", tags=["ai"])

@api_router.get("/health", tags=["system"])
def health_check():
    return {"status": "ok"}

@api_router.get("/system/health", tags=["system"])
def system_health_check():
    return {"status": "ok"}

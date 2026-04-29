from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.agent import router as agent_router
from api.routes.health import router as health_router
from api.routes.memory import router as memory_router
from api.routes.proactive import router as proactive_router
from api.routes.tools import router as tools_router
from api.websocket import register_websocket_routes
from config import get_settings
from db.postgres import get_database
from tasks.runner import get_background_runner

settings = get_settings()

app = FastAPI(
    title="Personal AI Companion API",
    version="0.1.0",
    summary="Voice-first backend for a continuous personal AI companion",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)
app.include_router(health_router)
app.include_router(memory_router)
app.include_router(proactive_router)
app.include_router(tools_router)
register_websocket_routes(app)


@app.on_event("startup")
async def startup() -> None:
    await get_database().open()
    await get_background_runner().start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await get_background_runner().stop()
    await get_database().close()


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "environment": settings.environment,
        "status": "ok",
    }

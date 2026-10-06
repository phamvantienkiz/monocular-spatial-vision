"""Main FastAPI Application Entrypoint.

Follows fastapi-backend-scaffold architecture invariants.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.middlewares import register_middlewares
from app.api.v1.router import api_v1_router
from app.services.ingest_service import IngestService
from app.services.model_service import ModelService

ingest_service = IngestService(port=settings.ingest_port, buffer_size=settings.ring_buffer_size)
model_service = ModelService(engine_path=settings.model_engine_path, conf_thresh=settings.confidence_threshold)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and shutdown lifecycle hooks."""
    setup_logging(settings.log_level)
    logger.info("Initializing Monocular Perception Backend on %s:%d...", settings.api_host, settings.api_port)

    # Startup hooks
    # TODO for Students: Start ingest_service.start() and model_service.load_model()
    yield

    # Shutdown hooks
    logger.info("Shutting down perception backend services...")
    ingest_service.stop()


app = FastAPI(
    title="Monocular Spatial Vision Backend",
    description="Jetson AGX Xavier perception engine and Web HUD service",
    version="0.1.0",
    lifespan=lifespan,
)

# Register cross-cutting middlewares
register_middlewares(app)

# Mount API routers
app.include_router(api_v1_router)


@app.get("/health", tags=["Health"])
def health_check():
    """Liveness probe endpoint."""
    return {"status": "ok", "env": settings.env, "version": "0.1.0"}


# Mount static HUD assets if directory exists
static_hud_dir = os.path.join(os.path.dirname(__file__), "static", "hud")
if os.path.isdir(static_hud_dir):
    app.mount("/hud", StaticFiles(directory=static_hud_dir, html=True), name="hud")


@app.get("/", include_in_schema=False)
def root():
    """Redirects root URL to the operator HUD."""
    return RedirectResponse(url="/hud/")

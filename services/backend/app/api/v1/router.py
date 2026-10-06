"""Aggregated API v1 router."""

from fastapi import APIRouter
from app.api.v1.endpoints import stream, telemetry, benchmark, system

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(stream.router, tags=["Stream"])
api_v1_router.include_router(telemetry.router, tags=["Telemetry"])
api_v1_router.include_router(benchmark.router, tags=["Benchmark"])
api_v1_router.include_router(system.router, tags=["System"])

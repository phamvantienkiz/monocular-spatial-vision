"""Middleware registration for FastAPI application."""

from fastapi import FastAPI
from app.middlewares.cors import setup_cors_middleware
from app.middlewares.request_id import RequestIdMiddleware
from app.middlewares.logging import LoggingMiddleware
from app.middlewares.error_handler import ErrorHandlerMiddleware


def register_middlewares(app: FastAPI) -> None:
    """Registers all cross-cutting middlewares in correct execution order."""
    setup_cors_middleware(app)
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIdMiddleware)

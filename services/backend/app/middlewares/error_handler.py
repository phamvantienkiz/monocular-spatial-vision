"""Global exception catch-all middleware."""

import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("monocular_backend.errors")


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Safely catches unhandled exceptions and returns structured 500 JSON."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            logger.exception("Unhandled server exception during request %s %s: %s", request.method, request.url.path, exc)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "detail": str(exc),
                    "request_id": getattr(request.state, "request_id", None),
                },
            )

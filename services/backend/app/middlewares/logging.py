"""Request timing and logging middleware."""

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("monocular_backend.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming requests with processing duration."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time_ms = (time.perf_counter() - start_time) * 1000.0

        response.headers["X-Process-Time"] = f"{process_time_ms:.2f}ms"
        logger.info(
            "%s %s -> status=%d duration=%.2fms",
            request.method,
            request.url.path,
            response.status_code,
            process_time_ms,
        )
        return response

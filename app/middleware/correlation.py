import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import request_id_ctx, tenant_id_ctx


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate X-Request-ID
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token_req = request_id_ctx.set(req_id)
        token_tenant = tenant_id_ctx.set(None)

        start_time = time.perf_counter()
        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            
            # Attach tracing headers to outbound response
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Process-Time-Ms"] = str(duration_ms)
            return response
        finally:
            request_id_ctx.reset(token_req)
            tenant_id_ctx.reset(token_tenant)
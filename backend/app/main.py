import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.api.auth import router as auth_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers


settings = get_settings()
app = FastAPI(title="AI for Digital Infrastructure & Governance API", version="1.0.0", docs_url="/docs" if settings.environment != "production" else None,
              redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                   allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Dev-User"])
install_error_handlers(app)
limits: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def request_controls(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    if request.url.path.startswith("/api/"):
        now = time.monotonic()
        client = request.client.host if request.client else "unknown"
        bucket = limits[client]
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_per_minute:
            return JSONResponse(status_code=429, content={"error": {"code": "rate_limited", "message": "Request limit reached", "request_id": request.state.request_id}})
        bucket.append(now)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


app.include_router(v1_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error",
            "message": "Request data is invalid", "request_id": getattr(request.state, "request_id", None)}})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "unauthenticated", 403: "forbidden", 404: "not_found", 413: "payload_too_large"}.get(exc.status_code, "request_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request could not be completed"
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)}})

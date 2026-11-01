"""FastAPI application entry point.

Run from quantum-pqc/:
    uvicorn api.main:app --reload --port 8000
OpenAPI docs: http://localhost:8000/docs
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.routes import API_VERSION, router
from api.services import ServiceError

logger = logging.getLogger("qfabric.api")

app = FastAPI(
    title="QFabric Quantum/PQC Service",
    version=API_VERSION,
    description="BB84 (Qiskit Aer), ML-DSA-65 and AES-256-GCM for QFabric. See docs/API_CONTRACT.md.",
)
app.include_router(router)


def _error(status_code: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


@app.exception_handler(ServiceError)
async def _service_error(_: Request, exc: ServiceError) -> JSONResponse:
    return _error(exc.status_code, exc.code, exc.message, exc.details)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Report field locations and messages only; never echo input values
    # (they may contain documents or signatures).
    fields = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
    return _error(422, "VALIDATION_ERROR", "request validation failed", {"fields": fields})


@app.exception_handler(NotImplementedError)
async def _not_implemented(_: Request, exc: NotImplementedError) -> JSONResponse:
    return _error(501, "NOT_IMPLEMENTED", f"{exc} is not implemented yet")


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error")  # stack trace to server log only
    return _error(500, "INTERNAL_ERROR", "internal error")

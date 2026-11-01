"""HTTP routes for /api/v1. Keep handlers thin: validate (Pydantic), call
the service layer, return the response model."""

from __future__ import annotations

from fastapi import APIRouter, Path

from api import schemas, services
from api.schemas import ErrorResponse

API_VERSION = "0.1.0"

_errors = {
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    501: {"model": ErrorResponse},
}

router = APIRouter(prefix="/api/v1", responses=_errors)


@router.get("/health", response_model=schemas.HealthResponse, tags=["health"])
def health() -> schemas.HealthResponse:
    components = services.component_status()
    status = "ok" if all(v == "available" for v in components.values()) else "degraded"
    return schemas.HealthResponse(status=status, version=API_VERSION, components=components,
                                  versions=services.component_versions())


@router.post("/organizations/register", response_model=schemas.OrganizationResponse, status_code=201, tags=["organizations"])
def register_organization(req: schemas.RegisterOrganizationRequest):
    return services.register_organization(req)


@router.get("/organizations/{org_id}", response_model=schemas.OrganizationResponse, tags=["organizations"])
def get_organization(org_id: str = Path(pattern=r"^[A-Za-z0-9_-]{1,64}$")):
    return services.get_organization(org_id)


@router.post("/mldsa/sign", response_model=schemas.SignResponse, tags=["ml-dsa"])
def mldsa_sign(req: schemas.SignRequest):
    return services.sign_message(req)


@router.post("/mldsa/verify", response_model=schemas.VerifyResponse, tags=["ml-dsa"])
def mldsa_verify(req: schemas.VerifyRequest):
    return services.verify_signature(req)


@router.post("/bb84/execute", response_model=schemas.BB84Response, tags=["bb84"])
def bb84_execute(req: schemas.BB84ExecuteRequest):
    return services.execute_bb84(req)


@router.post("/bb84/simulate-attack", response_model=schemas.BB84Response, tags=["bb84"])
def bb84_simulate_attack(req: schemas.BB84AttackRequest):
    return services.simulate_attack(req)


@router.post("/encryption/encrypt", response_model=schemas.EncryptResponse, tags=["encryption"])
def encryption_encrypt(req: schemas.EncryptRequest):
    return services.encrypt(req)


@router.post("/encryption/decrypt", response_model=schemas.DecryptResponse, tags=["encryption"])
def encryption_decrypt(req: schemas.DecryptRequest):
    return services.decrypt(req)


@router.post("/secure-transfer", response_model=schemas.SecureTransferResponse, tags=["secure-transfer"])
def secure_transfer(req: schemas.SecureTransferRequest):
    return services.secure_transfer(req)

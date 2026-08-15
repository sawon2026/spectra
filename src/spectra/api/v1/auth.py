"""Auth session API — create/revoke sessions; never logs tokens."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from spectra.api.deps import Principal, get_principal
from spectra.auth.session import Role, get_auth_service

router = APIRouter()


class LoginIn(BaseModel):
    subject: str = Field(..., min_length=1, max_length=128)
    role: str = "researcher"


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    subject: str
    expires_hint: str = "24h"


class MeOut(BaseModel):
    subject: str
    role: str
    offline: bool


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn) -> LoginOut:
    auth = get_auth_service()
    try:
        role = Role(body.role)
    except ValueError:
        role = Role.RESEARCHER
    token, sess = auth.create_session(body.subject, role=role)
    return LoginOut(
        access_token=token,
        role=sess.role.value,
        subject=sess.subject,
    )


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Bearer token required")
    token = authorization.removeprefix("Bearer ").strip()
    ok = get_auth_service().revoke(token)
    return {"revoked": ok}


@router.get("/me", response_model=MeOut)
def me(principal: Principal = Depends(get_principal)) -> MeOut:
    return MeOut(subject=principal.subject, role=principal.role, offline=principal.offline)

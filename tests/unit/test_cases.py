"""Case and scope lifecycle tests."""

from __future__ import annotations

import pytest

from spectra.cases.service import CaseService
from spectra.models.case import CaseCreate, CaseStatus
from spectra.models.scope import AuthStatus, NetworkProfile, ScopeCreate


def test_create_and_get(case_service: CaseService):
    c = case_service.create(CaseCreate(name="demo-case", description="test"))
    assert c.name == "demo-case"
    assert c.status == CaseStatus.DRAFT
    got = case_service.get(c.id)
    assert got is not None
    assert got.id == c.id


def test_duplicate_name_rejected(case_service: CaseService):
    case_service.create(CaseCreate(name="dup"))
    with pytest.raises(ValueError, match="already exists"):
        case_service.create(CaseCreate(name="dup"))


def test_name_path_traversal_rejected():
    with pytest.raises(ValueError):
        CaseCreate(name="../evil")
    with pytest.raises(ValueError):
        CaseCreate(name="foo/bar")


def test_scope_ready_when_granted_offline(case_service: CaseService):
    c = case_service.create(CaseCreate(name="scope-case"))
    scope = case_service.set_scope(
        ScopeCreate(
            case_id=c.id,
            auth_status=AuthStatus.GRANTED,
            network_profile=NetworkProfile.OFFLINE,
        )
    )
    assert scope.ready_for_act is True
    assert scope.auth_status == AuthStatus.GRANTED


def test_scope_not_ready_when_pending(case_service: CaseService):
    c = case_service.create(CaseCreate(name="pending-case"))
    scope = case_service.set_scope(
        ScopeCreate(
            case_id=c.id,
            auth_status=AuthStatus.PENDING,
            network_profile=NetworkProfile.OFFLINE,
        )
    )
    assert scope.ready_for_act is False


def test_update_status(case_service: CaseService):
    c = case_service.create(CaseCreate(name="status-case"))
    updated = case_service.update_status(c.id, CaseStatus.ACTIVE)
    assert updated.status == CaseStatus.ACTIVE

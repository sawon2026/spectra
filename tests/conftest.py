"""Pytest fixtures for Spectra."""

from __future__ import annotations

from pathlib import Path

import pytest

from spectra.capabilities.registry import CapabilityRegistry, seed_builtin_capabilities
from spectra.cases.service import CaseService
from spectra.core.config import SpectraSettings
from spectra.core.db import init_db, reset_db_for_tests
from spectra.events.bus import EventBus
from spectra.evidence.service import EvidenceService
from spectra.policy.engine import PolicyEngine


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "spectra-data"
    d.mkdir()
    return d


@pytest.fixture()
def settings(tmp_data_dir: Path) -> SpectraSettings:
    s = SpectraSettings(
        data_dir=tmp_data_dir,
        database_url=f"sqlite:///{tmp_data_dir / 'spectra.db'}",
        require_scope_for_execution=True,
        policy_strict=True,
        log_level="WARNING",
    )
    return s


@pytest.fixture()
def db(settings: SpectraSettings):
    reset_db_for_tests(settings)
    init_db(settings)
    return settings


@pytest.fixture()
def event_bus() -> EventBus:
    return EventBus(persist=True)


@pytest.fixture()
def policy(settings: SpectraSettings) -> PolicyEngine:
    return PolicyEngine(settings=settings)


@pytest.fixture()
def capability_registry(db) -> CapabilityRegistry:
    reg = CapabilityRegistry()
    seed_builtin_capabilities(reg)
    return reg


@pytest.fixture()
def case_service(db, event_bus) -> CaseService:
    return CaseService(event_bus=event_bus)


@pytest.fixture()
def evidence_service(db, event_bus) -> EvidenceService:
    return EvidenceService(event_bus=event_bus)

"""Pytest fixtures for Spectra."""

from __future__ import annotations

from pathlib import Path

import pytest

from spectra.capabilities.registry import CapabilityRegistry, seed_builtin_capabilities
from spectra.cases.service import CaseService
from spectra.core.config import SpectraSettings
from spectra.core.db import reset_db_for_tests
from spectra.events.bus import EventBus
from spectra.evidence.service import EvidenceService
from spectra.policy.engine import PolicyEngine


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    return tmp_path / "spectra-data"


@pytest.fixture()
def settings(tmp_data_dir: Path) -> SpectraSettings:
    s = SpectraSettings(
        data_dir=tmp_data_dir,
        environment="test",
        log_level="WARNING",
        require_scope_for_execution=True,
        allow_network_by_default=False,
    )
    s.ensure_data_dir()
    return s


@pytest.fixture()
def db(settings: SpectraSettings):
    reset_db_for_tests(settings)
    yield
    # cleanup handled by tmp_path


@pytest.fixture()
def event_bus(db) -> EventBus:
    return EventBus(persist=True)


@pytest.fixture()
def policy(event_bus: EventBus) -> PolicyEngine:
    return PolicyEngine(event_bus=event_bus)


@pytest.fixture()
def case_service(event_bus: EventBus, db) -> CaseService:
    return CaseService(event_bus=event_bus)


@pytest.fixture()
def capability_registry(event_bus: EventBus, db) -> CapabilityRegistry:
    reg = CapabilityRegistry(event_bus=event_bus)
    seed_builtin_capabilities(reg)
    return reg


@pytest.fixture()
def evidence_service(event_bus: EventBus, db) -> EvidenceService:
    return EvidenceService(event_bus=event_bus)

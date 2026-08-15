"""Capability registry tests."""

from __future__ import annotations

from spectra.capabilities.registry import CapabilityRegistry
from spectra.models.capability import RiskLevel


def test_seed_and_list(capability_registry: CapabilityRegistry):
    caps = capability_registry.list()
    names = {c.name for c in caps}
    assert "file-info" in names
    assert "hash-compute" in names


def test_get(capability_registry: CapabilityRegistry):
    c = capability_registry.get("file-info")
    assert c is not None
    assert c.risk_level == RiskLevel.NONE

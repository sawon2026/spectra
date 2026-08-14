"""Capability registry tests."""

from spectra.capabilities.registry import CapabilityRegistry, seed_builtin_capabilities


def test_seed_builtins(capability_registry):
    names = {c.name for c in capability_registry.list()}
    assert "file-info" in names
    assert "hash-compute" in names


def test_get_unknown(capability_registry):
    assert capability_registry.get("does-not-exist") is None

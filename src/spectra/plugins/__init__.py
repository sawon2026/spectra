"""Plugin interfaces — stable extension points without marketplace complexity."""

from spectra.plugins.base import (
    PluginKind,
    PluginManifest,
    PluginRegistry,
    validate_manifest,
)

__all__ = [
    "PluginKind",
    "PluginManifest",
    "PluginRegistry",
    "validate_manifest",
]

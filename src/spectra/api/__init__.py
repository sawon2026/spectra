"""Spectra HTTP API — FastAPI boundary over the existing core.

The API never bypasses PolicyEngine. Web clients cannot execute
arbitrary commands; all capability execution flows through the same
policy-gated backend used by the CLI.
"""

from spectra.api.app import create_app

__all__ = ["create_app"]

# Plugin / Adapter Guide (SDK v2)

## Architecture

Plugins in Spectra are **manifest + capability registration** contracts.
There is **no** arbitrary dynamic code loading from untrusted paths and
**no** remote plugin marketplace.

```
PluginManifest → PluginRegistry.register
                      ↓
              CapabilityRegistry (names only)
                      ↓
              PolicyEngine (sole execution gate)
                      ↓
              ToolAdapter.execute (shell=False)
```

**Plugin enablement ≠ execution authorization.**

## Manifest schema

| Field | Type | Notes |
|-------|------|-------|
| name | string | No path separators |
| version | string | Semver-like |
| kind | enum | tool_adapter, parser, capability, … |
| capabilities | string[] | Registry names |
| offline_safe | bool | Prefer true |
| requires_network | bool | Default false |

### Forbidden manifest fields

`shell`, `command`, `sudo`, `privilege_escalate`, `policy_override`

## Lifecycle & health

```python
from spectra.plugins.base import (
    PluginRegistry, PluginHealthStatus, validate_manifest
)

reg = PluginRegistry()
reg.register({
    "name": "example-hash-helper",
    "version": "0.1.0",
    "kind": "tool",
    "capabilities": ["hash-compute"],
    "offline_safe": True,
})
reg.enable("example-hash-helper")
reg.set_health("example-hash-helper", PluginHealthStatus.OK, "ready")
```

## Writing an adapter

1. Subclass `ToolAdapter`
2. Define capability metadata (name, risk, inputs, auth)
3. Implement `is_available()` and `execute()`
4. Always call policy check before side effects
5. Use pure Python or `run_safe_command` (shell=False)
6. Register capability in `CapabilityRegistry`
7. Emit structured events; record evidence with hashes

## Never

- `shell=True`
- Bypass PolicyEngine
- Treat model text as FACT or EVIDENCE
- Log tokens, passwords, API keys
- Auto-download or exec remote code

## Testing

- Reject forbidden manifest fields
- Enable/disable does not grant PolicyEngine allow
- Health status is advisory only

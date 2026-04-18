# Security & Quality Checklist

Cross-reference of the assignment's Step-4 Security Checklist against the
actual code and tests in this repo.

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1 | Credentials are in environment variables, **not** in code | ✅ | `_device_params()` reads `DEVICE_HOST`, `DEVICE_USERNAME`, `DEVICE_PASSWORD` from `os.environ` and raises `RuntimeError` if any are missing. Static grep found zero hardcoded credentials. |
| 2 | All tool inputs are validated (regex for IPs, interface names, etc.) | ✅ | Three regex validators (`_INTERFACE_RE`, `_DESCRIPTION_RE`, `_SECTION_RE`) run **before** any device connection. Verified against 14 adversarial inputs including shell-injection, path traversal, control chars, and over-length strings. |
| 3 | Write tools confirm the change was applied (verification step) | ✅ | `configure_interface_description` reads back `show running-config interface … \| include description` after the config set, compares to the requested value, and returns `applied: true/false`. `save_config` checks for `[OK]` in the `write memory` output. |
| 4 | README documents what permissions/access the tools need | ✅ | See README.md "Permissions required" section (network egress, privileged-exec device account, local env access). |
| 5 | Tested with invalid inputs to make sure the server doesn't crash | ✅ | Validators raise `ValidationError` (a subclass of `ValueError`), which FastMCP converts to a clean error response. Verified with 14 bad inputs: all were rejected cleanly without touching the network. |

## Additional hardening beyond the checklist

| Hardening | Where |
|---|---|
| Narrow write surface (descriptions + save only; no shutdown, no IP change, no VLAN delete) | `server.py` tool selection |
| Connection errors wrapped as friendly `RuntimeError` rather than leaking Netmiko tracebacks | `_connect()` context manager |
| Output parsed to JSON via Netmiko TextFSM, with safe `{"raw": "..."}` fallback | `_safe_parse()`, `_as_json()` |
| `.env` is git-ignored; only `.env.example` with public DevNet values is committed | `.gitignore`, `.env.example` |
| stdio transport only — no network listener to attack | `mcp.run()` default |
| Credentials never appear in any tool's input or output schema | All tool signatures read from env, not args |

## Rubric self-assessment

| Rubric area | Weight | Self-assessment |
|---|---|---|
| Code repository (README + requirements + code) | 30% | Complete. README has setup, tools, Claude Desktop config, examples, troubleshooting. |
| Working demo | 30% | **Pending student action** — demo script is ready (`docs/demo-script.md`); record a 4-6 min screencast following it. |
| Write-up (architecture, challenges, security) | 20% | Complete. 2-page `.docx` at `docs/writeup.docx`. |
| Tool quality (validation, error handling, descriptions) | 20% | 7 tools > 5 required; every tool has a meaningful docstring; all write tools verify; all inputs validated. |

**Estimated grade band if demo is solid:** A (90–100%).

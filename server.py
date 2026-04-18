"""
Network MCP Server
------------------
A Model Context Protocol (MCP) server that exposes tools for interacting with
a Cisco IOS-XE network device over SSH. Built with FastMCP + Netmiko.

Exposed tools (7 total: 5 read + 2 write):
    Read:
        - get_device_info
        - get_interfaces
        - get_routes
        - get_arp_table
        - get_running_config
    Write:
        - configure_interface_description
        - save_config

Credentials are ALWAYS read from environment variables. They are never
accepted as tool arguments and never hardcoded.

Author: Ahmed (Sheridan College — Agent AI & Automation)
"""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)

# Load .env for local development. In production (Claude Desktop) the
# credentials come from the "env" block in claude_desktop_config.json.
load_dotenv()

mcp = FastMCP("network-mcp-server")


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

# Interface names like: GigabitEthernet0/0/1, Gi0/0, Loopback0, Vlan10,
# TenGigE0/0/0/1, Port-channel1, Ethernet1/1
_INTERFACE_RE = re.compile(r"^[A-Za-z][A-Za-z\-]{0,24}[0-9][0-9/\.:]{0,15}$")

# A conservative description: printable ASCII, no control chars, no shell
# metacharacters that could lead to command injection on the device CLI.
_DESCRIPTION_RE = re.compile(r"^[A-Za-z0-9 _\-.:,/()+=@#']{1,200}$")

# Running-config section filter (e.g. "interface GigabitEthernet1", "router bgp")
_SECTION_RE = re.compile(r"^[A-Za-z0-9 _\-/\.]{1,80}$")


class ValidationError(ValueError):
    """Raised when a tool argument fails validation."""


def _validate_interface(interface: str) -> str:
    if not isinstance(interface, str) or not _INTERFACE_RE.match(interface):
        raise ValidationError(
            f"Invalid interface name: {interface!r}. "
            "Expected format like 'GigabitEthernet1', 'Gi0/0/1', 'Loopback0'."
        )
    return interface


def _validate_description(description: str) -> str:
    if not isinstance(description, str) or not _DESCRIPTION_RE.match(description):
        raise ValidationError(
            "Invalid description. Must be 1-200 chars, alphanumerics plus "
            "space and ._-:,/()+=@#'. No control chars or shell metacharacters."
        )
    return description


def _validate_section(section: str) -> str:
    if not isinstance(section, str) or not _SECTION_RE.match(section):
        raise ValidationError(
            "Invalid section filter. Must be 1-80 chars, alphanumerics, "
            "spaces, dots, slashes, underscores or hyphens."
        )
    return section


# ---------------------------------------------------------------------------
# Device connection
# ---------------------------------------------------------------------------

def _device_params() -> dict[str, Any]:
    """Build Netmiko connection params from environment variables.

    Raises a clear RuntimeError if anything is missing.
    """
    required = ("DEVICE_HOST", "DEVICE_USERNAME", "DEVICE_PASSWORD")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + ". Set them in your shell or in Claude Desktop's mcpServers "
            '"env" block. See .env.example.'
        )

    return {
        "device_type": os.environ.get("DEVICE_TYPE", "cisco_xe"),
        "host": os.environ["DEVICE_HOST"],
        "port": int(os.environ.get("DEVICE_PORT", "22")),
        "username": os.environ["DEVICE_USERNAME"],
        "password": os.environ["DEVICE_PASSWORD"],
        "fast_cli": False,
        "conn_timeout": 20,
        "banner_timeout": 20,
        "auth_timeout": 20,
    }


@contextmanager
def _connect():
    """Context manager that yields an open Netmiko connection.

    Translates Netmiko exceptions into RuntimeError with friendly messages so
    the LLM can reason about them and surface them to the user.
    """
    params = _device_params()
    try:
        conn = ConnectHandler(**params)
    except NetmikoAuthenticationException as e:
        raise RuntimeError(
            f"Authentication to {params['host']} failed: {e}"
        ) from e
    except NetmikoTimeoutException as e:
        raise RuntimeError(
            f"Connection to {params['host']} timed out: {e}"
        ) from e
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            f"Unable to connect to {params['host']}: {e}"
        ) from e
    try:
        yield conn
    finally:
        try:
            conn.disconnect()
        except Exception:  # noqa: BLE001
            pass


def _safe_parse(conn, command: str) -> Any:
    """Run a `show` command and try to parse it with TextFSM into structured
    data. Falls back to raw text if no TextFSM template matches.
    """
    try:
        parsed = conn.send_command(command, use_textfsm=True)
        if isinstance(parsed, (list, dict)):
            return parsed
    except Exception:  # noqa: BLE001
        pass
    # Fallback: raw CLI text
    return conn.send_command(command)


def _as_json(payload: Any) -> str:
    """Serialize tool output as pretty JSON string (MCP tools return text)."""
    if isinstance(payload, str):
        # Already a string — wrap it so the LLM gets consistent structure
        return json.dumps({"raw": payload}, indent=2)
    return json.dumps(payload, indent=2, default=str)


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_device_info() -> str:
    """Get basic information about the network device.

    Returns the hostname, hardware model, software version, uptime, and
    serial number parsed from `show version`. Use this tool first when you
    want to confirm which device you are talking to.

    Returns:
        JSON string with fields like hostname, hardware, version, uptime,
        serial, running_image.
    """
    with _connect() as conn:
        parsed = _safe_parse(conn, "show version")
        hostname = conn.send_command("show running-config | include ^hostname").strip()
        result: dict[str, Any] = {"hostname_line": hostname, "show_version": parsed}
    return _as_json(result)


@mcp.tool()
def get_interfaces() -> str:
    """List all interfaces on the device with their status, IP address,
    description, and line protocol state.

    Parses `show ip interface brief` and `show interfaces description` to
    produce a structured list. Use this to inspect which interfaces exist,
    which are up, and which have IPs assigned.

    Returns:
        JSON string: a list of interface objects with keys like interface,
        ip_address, status, protocol, description.
    """
    with _connect() as conn:
        brief = _safe_parse(conn, "show ip interface brief")
        desc = _safe_parse(conn, "show interfaces description")
        result = {"ip_interface_brief": brief, "interface_descriptions": desc}
    return _as_json(result)


@mcp.tool()
def get_routes() -> str:
    """Retrieve the IPv4 routing table from the device.

    Parses `show ip route` into structured entries (protocol, network,
    mask, next-hop, interface, metric). Use this to troubleshoot
    reachability or to confirm that a route you just added is present.

    Returns:
        JSON string of route entries.
    """
    with _connect() as conn:
        routes = _safe_parse(conn, "show ip route")
    return _as_json({"routes": routes})


@mcp.tool()
def get_arp_table() -> str:
    """Retrieve the ARP table (IP-to-MAC mappings) from the device.

    Use this to confirm a neighbor is reachable at Layer 2, or to
    troubleshoot duplicate-IP or MAC-flap issues.

    Returns:
        JSON string: a list of ARP entries with fields like address,
        age, mac, type, interface.
    """
    with _connect() as conn:
        arp = _safe_parse(conn, "show ip arp")
    return _as_json({"arp_entries": arp})


@mcp.tool()
def get_running_config(section: str | None = None) -> str:
    """Retrieve the running configuration.

    If `section` is omitted, returns the entire running-config. If provided,
    returns only the matching section (e.g. section='interface
    GigabitEthernet1' or section='router bgp').

    Args:
        section: Optional section filter. Must match
            ^[A-Za-z0-9 _\\-/\\.]{1,80}$. Examples: 'interface Loopback0',
            'router ospf 1', 'line vty 0 4'.

    Returns:
        JSON string with the config text.
    """
    if section is not None:
        section = _validate_section(section)
    with _connect() as conn:
        if section:
            output = conn.send_command(f"show running-config | section {section}")
        else:
            output = conn.send_command("show running-config")
    return _as_json({"section": section, "config": output})


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------

@mcp.tool()
def configure_interface_description(interface: str, description: str) -> str:
    """Set the description on an interface, then verify the change was
    applied by reading it back.

    This is a WRITE tool — it modifies the running configuration on the
    device. The change is not persisted across reloads until `save_config`
    is called.

    Args:
        interface: Interface name, e.g. 'GigabitEthernet1', 'Loopback0'.
            Validated against ^[A-Za-z][A-Za-z\\-]{0,24}[0-9][0-9/\\.:]{0,15}$.
        description: New description, 1-200 chars. Safe printable ASCII
            only — no control chars or shell metacharacters.

    Returns:
        JSON string with fields: interface, requested_description,
        applied (bool), device_output, verification.
    """
    interface = _validate_interface(interface)
    description = _validate_description(description)

    commands = [
        f"interface {interface}",
        f"description {description}",
    ]

    with _connect() as conn:
        # Apply the config
        conn.enable()  # ensure privileged exec mode (no-op if already there)
        output = conn.send_config_set(commands)

        # Verify by reading it back
        verify_cmd = (
            f"show running-config interface {interface} | include ^ description"
        )
        verification = conn.send_command(verify_cmd).strip()

    expected = f"description {description}"
    applied = expected in verification

    return _as_json({
        "interface": interface,
        "requested_description": description,
        "applied": applied,
        "device_output": output,
        "verification": verification,
    })


@mcp.tool()
def save_config() -> str:
    """Persist the running configuration to the startup configuration.

    Equivalent to `copy running-config startup-config`. Call this after a
    successful write tool to ensure the change survives a device reload.

    This is a WRITE tool — it modifies NVRAM on the device.

    Returns:
        JSON string with fields: saved (bool), device_output.
    """
    with _connect() as conn:
        conn.enable()
        # `write memory` is the short form; it returns text like
        # "Building configuration...\n[OK]" on success.
        output = conn.send_command_timing(
            "write memory",
            strip_prompt=False,
            strip_command=False,
            read_timeout=30,
        )

    saved = "[OK]" in output or "OK" in output
    return _as_json({"saved": saved, "device_output": output})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Stdio transport — this is what Claude Desktop connects to.
    mcp.run()

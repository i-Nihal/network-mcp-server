# Network MCP Server

A Model Context Protocol (MCP) server that lets an AI agent interact with a
Cisco IOS-XE network device over SSH. Built in Python with
[FastMCP](https://github.com/modelcontextprotocol/python-sdk) and
[Netmiko](https://github.com/ktbyers/netmiko).

The server exposes **7 tools** (5 read + 2 write), each with strict input
validation and clear descriptions so an LLM agent can discover and use them
autonomously.

> Course: Agent AI & Automation — Sheridan College
> Author: Ahmed
> Instructor: Sebastian

---

## Table of contents

1. [Lab environment](#lab-environment)
2. [Install](#install)
3. [Run the server](#run-the-server)
4. [Tools](#tools)
5. [Connect to Claude Desktop](#connect-to-claude-desktop)
6. [Example interactions](#example-interactions)
7. [Permissions required](#permissions-required)
8. [Security notes](#security-notes)
9. [Troubleshooting](#troubleshooting)

---

## Lab environment

This project targets Cisco's **Always-On IOS-XE DevNet Sandbox**. It is free,
publicly reachable, requires no reservation, and is always up.

| Setting     | Value                              |
|-------------|------------------------------------|
| Host        | `sandbox-iosxe-latest-1.cisco.com` |
| Port        | `22` (SSH)                         |
| Username    | `admin`                            |
| Password    | `C1sco12345`                       |
| Device type | Cisco IOS-XE (Catalyst 8000v)      |

Reference: [Cisco DevNet — Always-On Sandboxes](https://devnetsandbox.cisco.com/DevNet/).

**Quick connectivity check from your machine:**

```bash
ssh admin@sandbox-iosxe-latest-1.cisco.com
# password: C1sco12345
```

You should land at `Router#` (or similar) prompt. If this works, the MCP
server will work too.

> The sandbox is shared. Please keep changes small and non-disruptive
> (e.g. only edit interface descriptions, don't shut interfaces or change IPs).

---

## Install

Requires **Python 3.10+**.

```bash
# 1. Clone / copy the project
cd network-mcp-server

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate    # on Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

Dependencies:

- `mcp[cli]` — MCP Python SDK (provides `FastMCP`)
- `netmiko` — multi-vendor SSH/CLI library
- `python-dotenv` — loads `.env` for local dev

---

## Run the server

### Option A — standalone (for local testing)

```bash
cp .env.example .env
# edit .env if your lab uses different credentials

python server.py
```

The server runs over **stdio**, so it waits on stdin for MCP JSON-RPC
messages. In practice you won't invoke it by hand — you'll connect Claude
Desktop (see below) or the `mcp` dev CLI.

### Option B — interactive dev inspector

```bash
mcp dev server.py
```

This opens the MCP Inspector in your browser where you can list tools and
call them manually.

---

## Tools

### Read tools

| Tool | Description |
|---|---|
| `get_device_info` | Hostname, model, software version, uptime, serial. Parses `show version`. |
| `get_interfaces` | All interfaces with status, IP, description. Parses `show ip interface brief` + `show interfaces description`. |
| `get_routes` | IPv4 routing table. Parses `show ip route` into structured entries. |
| `get_arp_table` | IP-to-MAC mappings. Parses `show ip arp`. |
| `get_running_config` | Full running config, or a single section (e.g. `interface GigabitEthernet1`). Takes optional `section` arg. |

### Write tools

| Tool | Description |
|---|---|
| `configure_interface_description` | Sets a description on an interface and **verifies** the change was applied by reading it back. Args: `interface`, `description`. |
| `save_config` | Runs `copy running-config startup-config` to persist changes across reload. |

All tool outputs are JSON strings so the LLM can reason over structured
data. When Netmiko's TextFSM parsers can't handle an output, the server
falls back to raw CLI text inside a `{"raw": "..."}` wrapper.

---

## Connect to Claude Desktop

1. Locate Claude Desktop's config file:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`

2. Merge the block below into the file (use the full **absolute** path to
   your `server.py`):

```json
{
  "mcpServers": {
    "network-mcp-server": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/network-mcp-server/server.py"],
      "env": {
        "DEVICE_HOST": "sandbox-iosxe-latest-1.cisco.com",
        "DEVICE_PORT": "22",
        "DEVICE_USERNAME": "admin",
        "DEVICE_PASSWORD": "C1sco12345",
        "DEVICE_TYPE": "cisco_xe"
      }
    }
  }
}
```

A ready-to-copy version lives in `claude_desktop_config.example.json`.

3. **Fully quit and reopen Claude Desktop.** (Just closing the window is
   not enough — it keeps the MCP process alive.)

4. In a new chat, click the 🛠️ / tools icon. You should see
   `network-mcp-server` listed with 7 tools.

---

## Example interactions

Once connected, try these prompts:

> **"What device am I connected to? Give me its hostname, model, and IOS
> version."**
> The agent will call `get_device_info`.

> **"List all interfaces that currently have an IP address assigned."**
> The agent will call `get_interfaces` and filter the results.

> **"Show me the default route."**
> The agent will call `get_routes` and pick the entry with network `0.0.0.0`.

> **"Set the description on GigabitEthernet2 to 'managed by MCP demo',
> then confirm the change was applied."**
> The agent will call `configure_interface_description`, then (optionally)
> `get_running_config` with `section='interface GigabitEthernet2'` to
> double-check.

> **"Save the running config to startup."**
> The agent will call `save_config`.

---

## Permissions required

The MCP server needs:

1. **Network egress** from the host machine to the device's SSH port
   (TCP/22 by default). On corporate networks you may need a VPN or proxy.
2. A device account with **privileged exec** rights — the DevNet sandbox's
   `admin` account is already enable-level. If you use your own device,
   the account must be able to enter `config t` and issue `write memory`.
3. Local **read access** to the `.env` file or equivalent environment
   variables set by Claude Desktop.

The server does **not** need root/admin on your workstation.

---

## Security notes

- **Credentials are never hardcoded.** They come from environment variables
  (`DEVICE_USERNAME`, `DEVICE_PASSWORD`). If any required env var is missing
  the server refuses to connect and returns a clear error.
- **`.env` is git-ignored.** A `.env.example` (with safe-to-share DevNet
  sandbox values) is provided instead.
- **Input validation on every tool.** Interface names, descriptions, and
  config-section filters are all regex-validated before reaching the device
  CLI. Shell metacharacters (`;`, `|`, backtick, newline, null byte) are
  rejected.
- **Credentials are never exposed as tool arguments.** The LLM cannot
  read, log, or exfiltrate them — it only sees tool outputs.
- **Write tools include verification.** `configure_interface_description`
  reads the config back after applying the change and reports
  `applied: true/false`.
- **Scope is narrow.** The two write tools can only change interface
  descriptions and save the config. Destructive operations (shutdown,
  IP-address change, VLAN delete, `erase startup-config`) are deliberately
  not exposed.

---

## Troubleshooting

**"Missing required environment variable(s)"**
You forgot to set `DEVICE_HOST` / `DEVICE_USERNAME` / `DEVICE_PASSWORD`.
Copy `.env.example` to `.env` or set them in Claude Desktop's `env` block.

**"Authentication to <host> failed"**
Double-check the password. If you changed the sandbox or use a different
device, make sure SSH is enabled and the account has privileged-exec
access.

**"Connection to <host> timed out"**
Network egress is blocked. Try `ssh admin@sandbox-iosxe-latest-1.cisco.com`
from the same machine. If that hangs too, your firewall/VPN is the issue.

**Claude Desktop doesn't show the server after editing the config**
Fully quit Claude Desktop (not just close the window) and reopen it. On
macOS: `Cmd+Q`. On Windows: right-click tray icon → Quit.

**Tool call returns raw text instead of parsed JSON**
This means Netmiko's TextFSM template didn't match the device output
(different IOS version, different platform). The server falls back to raw
CLI text in `{"raw": "..."}`. The agent can still reason over it; it's
just not structured.

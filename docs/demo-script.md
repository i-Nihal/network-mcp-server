# Demo Script — Network MCP Server

A step-by-step script for the required screencast. The rubric asks you
to demonstrate four things:

1. The agent discovers the available tools.
2. The agent uses **≥2 read tools** to gather information.
3. The agent makes a **configuration change through a write tool**.
4. The agent **verifies** the change was applied.

Total screencast length: **aim for 4–6 minutes.**

---

## 0. Pre-flight (don't record this part)

Before hitting record, confirm:

- [ ] `python server.py` runs without error when you set the env vars in
  a shell (kill it with Ctrl+C after it prints nothing — stdio mode is
  silent on stdin, that's normal).
- [ ] `ssh admin@sandbox-iosxe-latest-1.cisco.com` works from your
  machine.
- [ ] Claude Desktop is **fully quit and relaunched** after editing
  `claude_desktop_config.json`.
- [ ] A new Claude Desktop chat shows the 🛠️ icon with
  `network-mcp-server` and its 7 tools.
- [ ] Screen recorder is set to capture Claude Desktop + a terminal
  window (for the verification SSH step at the end).
- [ ] Audio source selected (if doing voice-over).

---

## 1. Intro (≈ 30 seconds)

**On camera / voice:**

> "This is Ahmed for the Agent AI & Automation assignment. I built an
> MCP server in Python that gives Claude Desktop seven tools for
> interacting with a Cisco IOS-XE router — five read tools and two
> write tools. The target device is the Cisco DevNet always-on IOS-XE
> sandbox. I'll show tool discovery, then two read operations, then a
> real configuration change with verification."

Show the project folder in your file browser or terminal for one second
so the viewer sees the structure.

---

## 2. Tool discovery (≈ 30 seconds)

In Claude Desktop, open a **new chat**, click the tools icon, and show
the `network-mcp-server` with its 7 tools expanded.

Then type this prompt:

> **"What tools do you have available from the network-mcp-server? List
> them and briefly describe what each one does."**

Claude will enumerate:

- `get_device_info`
- `get_interfaces`
- `get_routes`
- `get_arp_table`
- `get_running_config`
- `configure_interface_description`
- `save_config`

---

## 3. First read tool — device identity (≈ 45 seconds)

**Prompt:**

> **"I'd like to know what device I'm connected to. Give me the hostname,
> hardware model, IOS-XE version, and uptime."**

Claude calls `get_device_info`. Expand the tool call so the viewer can
see:
- the request (no arguments)
- the JSON response with parsed `show version` fields

Claude's reply should summarize in natural language (e.g. "You're
connected to a Cisco Catalyst 8000V running IOS-XE 17.x, up for N
days…").

---

## 4. Second read tool — interface inventory (≈ 60 seconds)

**Prompt:**

> **"List all interfaces that are currently administratively up and have
> an IP address assigned. I want a clean table."**

Claude calls `get_interfaces`. The tool returns parsed output from
`show ip interface brief` and `show interfaces description`. Claude
will filter and render it as a markdown table.

Pick **one** interface from that list to use in the write step —
usually `GigabitEthernet2` or `GigabitEthernet3` (avoid `Gi1`, which
is the management interface you're connected over).

**You can note aloud:**

> "I'll use GigabitEthernet2 for the configuration change. Let's first
> see what description it has right now."

**Follow-up prompt:**

> **"Show me the current running-config for GigabitEthernet2 only."**

Claude calls `get_running_config` with `section="interface
GigabitEthernet2"`. Note the current description (it might be empty or
say `ios-xe-mgmt` or similar).

---

## 5. Write tool — configuration change (≈ 60 seconds)

**Prompt:**

> **"Please set the description on GigabitEthernet2 to 'MCP-DEMO 2026 /
> Ahmed' and confirm the change was applied."**

Claude calls `configure_interface_description` with:
- `interface = "GigabitEthernet2"`
- `description = "MCP-DEMO 2026 / Ahmed"`

Expand the tool call. The response is JSON with:
- `applied: true`
- `device_output`: the CLI session from `interface … / description …`
- `verification`: the line read back from the running config

Claude will reply with something like _"Description applied
successfully. Verified via read-back."_

---

## 6. Verification — two ways (≈ 60 seconds)

### 6a. Agent-driven verification

**Prompt:**

> **"Double-check by reading the running-config for that interface
> again."**

Claude calls `get_running_config` with
`section="interface GigabitEthernet2"` and shows that the new
description is present. This proves the write is persistent in the
running config, not just an optimistic success message.

### 6b. Out-of-band verification (optional but impressive)

Switch to your terminal and SSH into the device directly:

```bash
ssh admin@sandbox-iosxe-latest-1.cisco.com
# password: C1sco12345

Router# show running-config interface GigabitEthernet2 | include description
 description MCP-DEMO 2026 / Ahmed
Router# exit
```

This proves the change is on the real device, independent of the agent
itself.

---

## 7. Optional — save to startup (≈ 20 seconds)

**Prompt:**

> **"Save the running configuration to startup so the change survives a
> reload."**

Claude calls `save_config`. Response JSON includes `saved: true` and
the `[OK]` output from `write memory`.

---

## 8. Cleanup (record this or mention it off-camera)

Leave the device in a clean state for the next user of the sandbox:

> **"Remove that description — set it to 'default'."**

Claude calls `configure_interface_description` again with
`description = "default"` (or whatever the original was). You can also
do this over SSH manually.

---

## 9. Outro (≈ 15 seconds)

> "That's the demo: tool discovery, two read tools, a verified write
> tool, and a save-to-startup. Full source code, README, and write-up
> are in the repository."

Stop recording.

---

## Talking points for the voice-over

If you want to sound prepared, drop these in:

- **"Every tool output is JSON, because LLMs reason better over
  structured data than raw CLI text."** (mention when the first tool
  call comes back)
- **"Credentials are in the `env` block of Claude Desktop's MCP config
  — never hardcoded, never passed as tool arguments."** (mention during
  the write tool)
- **"The write tool reads its own change back, so the `applied` field
  reflects what's actually on the device, not what the CLI optimistically
  printed."** (mention during step 5)
- **"The interface-name argument is regex-validated before anything
  reaches SSH, so shell-injection strings are rejected at the
  boundary."** (optional — mention during step 5 if you want to flex on
  input validation)

---

## Fallback prompts (if Claude picks the wrong tool)

If Claude picks `get_running_config` for "what device is this?":

> **"Use the get_device_info tool specifically."**

If Claude refuses to run a write tool (e.g. asks for confirmation):

> **"Yes, please go ahead."** (or pre-approve the tool call in Claude
> Desktop's tool settings so it runs without prompting)

If a tool call times out:

- Hit "retry" in Claude Desktop, or
- Verify the sandbox is reachable: `ssh admin@sandbox-iosxe-latest-1.cisco.com`

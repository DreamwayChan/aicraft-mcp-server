# AICraft MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Model Context Protocol server that gives AI agents access to **injection molding process optimization**: first-shot process recommendation and defect-driven tuning.

> This is a thin MCP client. All calculation, authentication, and billing happen on the hosted HTTPS API. No process data or algorithm code runs locally.

## What it does

Injection molding engineers need two things: a sensible starting set of machine parameters before a trial run, and corrections when the trial shows defects. This server exposes both as MCP tools, backed by a self-developed rule engine with explainable reasoning.

| Tool | What it does | Cost |
|---|---|---|
| `schema` | Free catalog of fields, units, defect codes, and error codes | Free |
| `first_shot` | Recommend initial process parameters from material, part, and machine data | 1 API call |
| `optimize` | Adjust current parameters for an observed defect | 1 API call |

The paid tools require a subscription API key. Get one at https://aicraft4injection.com ($19/month, 1000 calls). The `schema` tool works without a key so agents can discover the contract before paying.

## Requirements

- Python 3.10+
- An API key from https://aicraft4injection.com (for paid tools)

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set two environment variables:

```bash
export AICRAFT_API_KEY="sk_your_key_here"                       # required for paid tools
export AICRAFT_BASE_URL="https://aicraft4injection.com"         # optional, this is the default
```

## Usage with MCP clients

Add this server to your MCP client configuration (Claude Desktop, Cursor, Cline, etc.):

```json
{
  "mcpServers": {
    "aicraft": {
      "command": "python",
      "args": ["/absolute/path/to/agent-mcp-server/server.py"],
      "env": {
        "AICRAFT_API_KEY": "sk_your_key_here",
        "AICRAFT_BASE_URL": "https://aicraft4injection.com"
      }
    }
  }
}
```

Restart the client. Three tools should appear: `schema`, `first_shot`, `optimize`.

## Tool reference

### `schema`

No arguments. Returns field groups, default units (mm, mm/s, MPa, rpm, °C, s), valid defect codes, and error codes.

### `first_shot`

Requires three fields (the engine cannot compute without them):

| Field | Meaning |
|---|---|
| `polymer.polymer_abbreviation` | Material short name, e.g. `PC`, `ABS` |
| `mold.product_ave_thickness` | Average wall thickness in mm (0 < value < 50) |
| `machine.injector.injector_screw_diameter_mm` | Screw diameter in mm (> 0) |

Recommended but optional: melt density, back pressure, drying temperature, gate thickness, clamp force, injection stroke, barrel temperature zones.

Example argument:

```json
{
  "polymer": {"polymer_abbreviation": "PC", "melt_density": 1.05},
  "mold": {"product_ave_thickness": 2.0, "gate_thickness": 1.2},
  "machine": {"machine_clamp_force_ton": 180,
              "injector": {"injector_screw_diameter_mm": 36}}
}
```

### `optimize`

Requires a defect and the current process parameters:

```json
{
  "defect_info": [{"desc": "FLASH", "level": "中等"}],
  "current_params": {"IP0": 90, "IV0": 40, "PP0": 50, "CT": 12}
}
```

`desc` accepts stable codes such as `SHORTSHOT`, `FLASH`, `SHRINKAGE`, `BURN`, `WELDLINE`, `WARPING` (25 codes in total — call `schema` for the full list). `level` accepts `轻微` / `中等` / `严重` or a number from 0 to 1.

## Design notes

- **Stdio transport**, protocol version `2024-11-05` for broad client compatibility.
- **No local computation.** The server forwards JSON-RPC tool calls to the hosted API; the engine stays on the operator's own infrastructure.
- **Stable error codes.** Every API response carries an `api_version` and a machine-readable `code` (e.g. `MISSING_FIELD`, `UNKNOWN_DEFECT`, `QUOTA_EXCEEDED`, `ENGINE_REJECTED`). Agents branch on `code`, not on prose.
- **No charge on invalid input.** Requests rejected by validation do not consume quota. Engine failures are refunded automatically.

A Streamable HTTP endpoint is also available for clients that prefer remote MCP: `https://aicraft4injection.com/mcp` (discovery document at `/.well-known/mcp.json`).

## Links

- Service: https://aicraft4injection.com
- Free field/defect catalog: https://aicraft4injection.com/v1/schema
- Short OpenAPI spec: https://aicraft4injection.com/openapi-tools.json
- LLM discovery file: https://aicraft4injection.com/llms.txt

## License

MIT

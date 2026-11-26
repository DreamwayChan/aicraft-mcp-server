# AICraft MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Model Context Protocol server that gives AI agents access to **injection molding process optimization**: first-shot process recommendation and defect-driven tuning.

> This is a thin MCP client. All calculation, authentication, and billing happen on the hosted HTTPS API. No process data or algorithm code runs locally.

## What it does

Injection molding engineers need two things: a sensible starting set of machine parameters before a trial run, and corrections when the trial shows defects. This server exposes both as MCP tools, backed by a self-developed rule engine with explainable reasoning.

| Tool | What it does | Cost |
|---|---|---|
| `schema` | Free catalog of fields, units, examples, defect codes, and error codes | Free |
| `first_shot` | Recommend initial process parameters from material, part, shot mass, and machine data | 1 API call |
| `optimize` | Adjust stored or current parameters for an observed defect | 1 API call |

The paid tools require a subscription API key. Get one at https://aicraft4injection.com ($19/month, 1000 calls). The `schema` tool works without a key so agents can discover the contract before paying.

## Connect via Remote HTTP or Local Stdio

### Option 1: Remote Streamable HTTP (no local installation)

Clients supporting Streamable HTTP MCP can connect directly to:

- **Endpoint**: `https://aicraft4injection.com/mcp`
- **Header**: `Authorization: Bearer sk_your_key_here`
- **Discovery card**: `https://aicraft4injection.com/.well-known/mcp.json`

### Option 2: Local Stdio

Requirements: Python 3.10+ and an API key from https://aicraft4injection.com (for paid tools).

```bash
pip install -r requirements.txt
```

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

No arguments. Returns field groups, full request examples, default units (mm, mm/s, MPa, rpm, °C, s), valid defect codes, parameter meanings, and error codes.

### `first_shot`

Requires three fields (the engine cannot compute without them):

| Field | Meaning |
|---|---|
| `polymer.polymer_abbreviation` | Material short name, e.g. `PC`, `PP`, `ABS` |
| `mold.product_ave_thickness` | Average wall thickness in mm (0 < value < 50) |
| `machine.injector.injector_screw_diameter_mm` | Screw diameter in mm (> 0) |

Strongly recommended fields:

- **`target_shot_weight_g`** (top-level total shot weight including runner, in g) — or `mold.single_cavity_part_weight_g` + `mold.cavity_num` + `mold.runner_weight`, or `mold.product_total_weight`. **Without shot mass, screw positions (`VPTL`, `MEL`, `IL*`) fall back to generic range midpoints instead of physically computed values.**
- **`business_id`** (your own job/mould ID, without any prefix, e.g. `"MOLD-A-100"`) — stores the process under your API key scope and returns `process_no` and `process_index_id` so subsequent `optimize` calls do not need to resend all ~50 parameters.
- Important field semantics: `machine_barrel_temperature_stage` is the **count of heating zones** (4 or 5), not a temperature in °C; `product_max_length` is the **longest melt flow length** in mm (typically 100–500), not wall thickness.

Example argument:

```json
{
  "business_id": "MOLD-A-100",
  "target_shot_weight_g": 55,
  "polymer": {
    "polymer_abbreviation": "PC",
    "melt_density": 1.05
  },
  "mold": {
    "product_ave_thickness": 2.0,
    "gate_thickness": 1.2,
    "product_max_length": 180
  },
  "machine": {
    "machine_clamp_force_ton": 180,
    "injector": {
      "injector_screw_diameter_mm": 36,
      "injector_max_injection_stroke_mm": 160,
      "machine_barrel_temperature_stage": 5
    }
  }
}
```

### `optimize`

Supports two input modes:

#### Option A (Preferred): Stored process via `business_id` or `process_no`

Pass the `business_id` used in `first_shot` (or the returned `process_no`) plus `defect_info`. The server automatically loads the full previous process from the archive, and optional machine measurements improve rule accuracy:

```json
{
  "business_id": "MOLD-A-100",
  "defect_info": [{"desc": "SHORTSHOT", "level": "moderate"}],
  "actual_mould_temp": 85,
  "actual_injection_peak_pressure": 112,
  "min_buffer_position": 4.5
}
```

Optional measurement fields: `actual_mould_temp`, `actual_injection_peak_pressure`, `actual_fast_injection_speed`, `min_buffer_position`, `actual_vp_position`, `actual_product_weight`.

#### Option B (Stateless fallback): Full `current_params`

If the previous shot was not stored with `business_id`, pass `current_params` containing **every** `key -> value` from `first_shot`'s `parameters` array (including `ML0`, `MEL`, `VPTL`, `IP0..2`, `IV0..2`, `IL0..2`, `PP0..1`, `PT0..1`, `PV0..1`, `BT1..4`, `MP0`, `MSR0`, `MBP0`, `CT`, `NT`). Do **not** send only a handful of keys (e.g. `NT`, `IP0`, `CT`) — omitting `ML0` causes screw-position collapse.

`desc` accepts 25 stable defect codes such as `SHORTSHOT`, `FLASH`, `SHRINKAGE`, `BURN`, `WELDLINE`, `WARPING` (call `schema` for the full list).

`level` accepts an English enum or a number from 0 to 1 (no Chinese values):

| Value | Meaning |
|---|---|
| `none` | No defect — the row is dropped |
| `mild` | Minor defect |
| `moderate` | Medium defect |
| `severe` | Serious defect |
| `critical` | Very serious defect |

The gateway translates these to the engine's internal severity values. Invalid levels are rejected with `400 INVALID_FIELD` and do not consume quota.

## Understanding the result

A successful call returns three layers, so you never have to guess what a code like `IP0` means:

1. **`summary`** — a one-paragraph, human-readable sentence. Read this aloud to the user.
2. **`parameters`** — one entry per process value with `key`, `name` (full English name), `value`, `unit`, and `group`. Use `name` when explaining a value.
3. **`data`** — the raw `key -> value` map, intended for writing settings back to a machine. Keys are abbreviations; humans should use `summary` or `parameters` instead.

When `business_id` or `process_no` is supplied, the response also includes `process_no` and `process_index_id`.

Example `parameters` entry:

```json
{"key": "NT", "name": "Nozzle temperature", "value": 280, "unit": "C", "group": "temperature"}
```

Common key groups (full dictionary for every key is available from the free `schema` tool under `parameters`):

| Prefix | Meaning |
|---|---|
| `NT`, `BT1`..`BT4` | Nozzle temperature, barrel temperature zones |
| `IP0`..`IP5` | Injection pressure, stage 0..5 |
| `IV0`..`IV5` | Injection velocity, stage 0..5 |
| `IL0`..`IL5` | Injection stroke end position, stage 0..5 |
| `PP0`..`PP4`, `PV0`..`PV4`, `PT0`..`PT4` | Holding pressure / velocity / time |
| `MP0`..`MP3`, `MSR0`..`MSR3`, `MBP0`..`MBP3`, `ML0`..`ML3` | Metering pressure / screw speed / back pressure / position |
| `VPTL`, `VPTT`, `VPTP`, `VPTV` | V/P switch position, time, pressure, velocity |
| `CT`, `IT`, `ID`, `MD`, `MEL` | Cooling time, injection time/delay, metering delay/end |
| `DPBM`..`DTBM`, `DPAM`..`DTAM` | Decompression before / after metering (pressure, velocity, distance, time) |

Default units: mm, mm/s, MPa, rpm, °C, s. A request can override them with `pressure_unit`, `velocity_unit`, `position_unit`, and `screw_rotation_unit`.

## Design notes

- **Stdio & Streamable HTTP**, protocol version `2024-11-05` for broad client compatibility.
- **Full JSON Schema tool definitions**, bundled in `openapi_tools.json` so AI agents see all required fields, shot-mass options, archive IDs, and 25 defect enums.
- **No local computation.** The server forwards JSON-RPC tool calls to the hosted API; the engine stays on the operator's own infrastructure.
- **Stable error codes.** Every API response carries an `api_version` and a machine-readable `code` (e.g. `MISSING_FIELD`, `UNKNOWN_DEFECT`, `QUOTA_EXCEEDED`, `ENGINE_REJECTED`). Agents branch on `code`, not on prose.
- **No charge on invalid input.** Requests rejected by validation do not consume quota. Engine failures are refunded automatically.

## Links

- Service: https://aicraft4injection.com
- Technical guide & FAQ: https://aicraft4injection.com/content
- Free field/defect catalog: https://aicraft4injection.com/v1/schema
- Short OpenAPI spec: https://aicraft4injection.com/openapi-tools.json
- LLM discovery file: https://aicraft4injection.com/llms.txt

## License

MIT

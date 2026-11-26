"""Expose schema, first-shot, and optimize as MCP tools over stdio.

The process reads AICRAFT_API_KEY and AICRAFT_BASE_URL. Calculation, quota,
and auth stay on the HTTPS gateway.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

Transport = Callable[[str, str, dict | None, dict], tuple[int, Any]]


def _request_schemas() -> dict[str, dict[str, Any]]:
    """Load tool input schemas from the bundled OpenAPI tools document.

    Keeps the stdio MCP tool contract in sync with the hosted Streamable HTTP
    endpoint (/mcp) and the spec Coze / GPT Actions / Dify import. Falls back to
    permissive schemas if the file is unavailable.
    """
    base = Path(__file__).resolve().parent
    candidates = (
        base / "openapi_tools.json",
        base.parent / "agent-api-starter" / "app" / "openapi_tools.json",
        base.parent / "app" / "openapi_tools.json",
    )
    out: dict[str, dict[str, Any]] = {}
    for path in candidates:
        if not path.is_file():
            continue
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
            for route, tool in (
                ("/v1/first-shot", "first_shot"),
                ("/v1/optimize", "optimize"),
            ):
                schema = (
                    spec["paths"][route]["post"]["requestBody"]["content"]
                    ["application/json"]["schema"]
                )
                out[tool] = schema
            if out:
                break
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return out


_SCHEMAS = _request_schemas()

_FIRST_SHOT_SCHEMA = _SCHEMAS.get(
    "first_shot", {"type": "object", "additionalProperties": True}
)
_OPTIMIZE_SCHEMA = _SCHEMAS.get(
    "optimize", {"type": "object", "additionalProperties": True}
)

_TOOLS = (
    {
        "name": "schema",
        "description": "Free catalog of input fields, returned parameter names (what each code like NT or IP0 means), defect codes, and error codes. Does not spend quota. Call this first if unsure about field names or units.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "first_shot",
        "description": (
            "Recommend a first-shot process before any trial. Costs 1 call. "
            "Required: polymer.polymer_abbreviation (material grade, e.g. PP, PC, ABS), "
            "mold.product_ave_thickness (average wall thickness in mm), "
            "machine.injector.injector_screw_diameter_mm (screw diameter in mm). "
            "CRITICAL - ASK THE USER FOR SHOT MASS: always ask for the total shot weight "
            "(part(s) plus runner) in grams and pass it as the TOP-LEVEL field "
            "target_shot_weight_g (e.g. 62). Alternatively pass mold.product_total_weight, "
            "or mold.single_cavity_part_weight_g + mold.cavity_num + mold.runner_weight. "
            "WITHOUT shot mass, VPTL/MEL/IL are range MIDPOINTS (e.g. VPTL=45, MEL=115) "
            "instead of physically computed values - the result will NOT be realistic. "
            "machine_barrel_temperature_stage is a COUNT of zones (4 or 5), NOT a temperature. "
            "product_max_length is the melt flow length in mm (100-500), not wall thickness. "
            "Also pass business_id (your own job ID, no prefix) so the result is stored and a "
            "later optimize call needs only business_id + defect_info; the result returns "
            "process_no and process_index_id."
        ),
        "inputSchema": _FIRST_SHOT_SCHEMA,
    },
    {
        "name": "optimize",
        "description": (
            "Adjust the current process for one observed defect. Costs 1 call. "
            "PREFERRED (option A): pass business_id (the same ID you used in first_shot) "
            "plus defect_info only - the server loads the stored previous process from "
            "the archive automatically, so you do NOT need to resend all parameters. "
            "Alternatively pass process_no (the value returned by first_shot). "
            "FALLBACK (option B): if the process was not stored, pass current_params with "
            "the COMPLETE process - copy EVERY key/value from the first_shot 'parameters' "
            "array as key->value pairs, including ML0, MEL, VPTL, all IP0/IP1/IP2, "
            "IV0/IV1/IV2, IL0/IL1/IL2, PP0/PP1, PT0/PT1, PV0/PV1, BT1..BT4, MP0, MSR0, "
            "MBP0, CT, NT and the stage counts. Passing only a few keys (e.g. NT, IP0, CT) "
            "produces wrong results. defect_info is an array of "
            "{desc: defect code, level: severity}. Call schema first for defect codes. "
            "Also pass available context (polymer_abbreviation, product_ave_thickness, "
            "injector_max_injection_pressure, actual_injection_peak_pressure) when known."
        ),
        "inputSchema": _OPTIMIZE_SCHEMA,
    },
)

_ROUTES = {
    "schema": ("GET", "/v1/schema"),
    "first_shot": ("POST", "/v1/first-shot"),
    "optimize": ("POST", "/v1/optimize"),
}


def call_tool(
    name: str,
    arguments: dict | None,
    transport: Transport,
    *,
    api_key: str,
) -> dict[str, Any]:
    route = _ROUTES.get(name)
    if route is None:
        return {"isError": True, "text": f"Unknown tool {name}."}
    method, path = route
    headers: dict[str, str] = {}
    if name != "schema":
        if not api_key:
            return {"isError": True, "text": "Set AICRAFT_API_KEY before calling a paid tool."}
        headers["Authorization"] = f"Bearer {api_key}"
    body = None if method == "GET" else dict(arguments or {})
    status, payload = transport(method, path, body, headers)
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return {"isError": status >= 400, "text": text}


def handle_message(
    message: dict[str, Any],
    *,
    transport: Transport | None = None,
    api_key: str = "",
) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _result(
            msg_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "aicraft", "version": "1"},
            },
        )
    if method == "tools/list":
        return _result(msg_id, {"tools": list(_TOOLS)})
    if method == "tools/call":
        params = message.get("params") or {}
        if transport is None:
            return _result(msg_id, {"content": [{"type": "text", "text": "No transport."}], "isError": True})
        outcome = call_tool(str(params.get("name") or ""), params.get("arguments") or {}, transport, api_key=api_key)
        return _result(
            msg_id,
            {"content": [{"type": "text", "text": outcome["text"]}], "isError": outcome["isError"]},
        )
    if msg_id is None:
        return None
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Unknown method {method}"}}


def _result(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _http_transport(base_url: str) -> Transport:
    import httpx

    def transport(method: str, path: str, body: dict | None, headers: dict) -> tuple[int, Any]:
        response = httpx.request(method, f"{base_url}{path}", json=body, headers=headers, timeout=60)
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        return response.status_code, payload

    return transport


def main() -> None:
    base_url = os.environ.get("AICRAFT_BASE_URL", "https://aicraft4injection.com").rstrip("/")
    api_key = os.environ.get("AICRAFT_API_KEY", "")
    transport = _http_transport(base_url)
    for line in sys.stdin:
        if not line.strip():
            continue
        reply = handle_message(json.loads(line), transport=transport, api_key=api_key)
        if reply is None:
            continue
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

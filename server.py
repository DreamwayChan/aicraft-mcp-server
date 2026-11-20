"""Expose schema, first-shot, and optimize as MCP tools over stdio.

The process reads AICRAFT_API_KEY and AICRAFT_BASE_URL. Calculation, quota,
and auth stay on the HTTPS gateway.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from typing import Any

Transport = Callable[[str, str, dict | None, dict], tuple[int, Any]]

_TOOLS = (
    {
        "name": "schema",
        "description": "Free catalog of fields, defect codes, and error codes. Does not spend quota.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "first_shot",
        "description": (
            "Recommend a first-shot process. Costs 1 call. "
            "Required: polymer.polymer_abbreviation, mold.product_ave_thickness, "
            "machine.injector.injector_screw_diameter_mm."
        ),
        "inputSchema": {"type": "object", "additionalProperties": True},
    },
    {
        "name": "optimize",
        "description": (
            "Adjust the current process for one defect. Costs 1 call. "
            "Required: defect_info with desc set to an engine code, and current_params."
        ),
        "inputSchema": {"type": "object", "additionalProperties": True},
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

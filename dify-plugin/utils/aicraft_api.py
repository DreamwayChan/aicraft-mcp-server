"""Shared HTTP client and Markdown sheet formatter for AICraft Dify Plugin."""

from __future__ import annotations

from typing import Any

import httpx

SCHEMA_ENDPOINT = "https://aicraft4injection.com/v1/schema"
FIRST_SHOT_ENDPOINT = "https://aicraft4injection.com/v1/first-shot"
OPTIMIZE_ENDPOINT = "https://aicraft4injection.com/v1/optimize"


def _build_headers(raw_credential: Any, *, json_body: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    if json_body:
        headers["Content-Type"] = "application/json"
    cleaned = str(raw_credential or "").strip().strip("'\"")
    if cleaned.lower().startswith("bearer "):
        cleaned = cleaned[7:].strip()
    if cleaned:
        headers["Authorization"] = f"Bearer {cleaned}"
    return headers


def verify_credentials_zero_cost(raw_credential: str) -> None:
    """Validate API key against AICraft gateway at zero quota consumption."""
    headers = _build_headers(raw_credential, json_body=True)
    if "Authorization" not in headers:
        raise ValueError("AICraft API key is required (starts with sk_...).")
    try:
        resp = httpx.post(
            "https://aicraft4injection.com/v1/first-shot",
            json={},
            headers=headers,
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise ValueError(f"Could not reach AICraft API: {exc.__class__.__name__}") from exc

    if resp.status_code == 401:
        raise ValueError("Invalid AICraft API key. Check your sk_... key from https://aicraft4injection.com.")
    if resp.status_code == 403:
        raise ValueError("API key is inactive or expired. Check your account at https://aicraft4injection.com.")
    if resp.status_code in (200, 400):
        return
    raise ValueError(f"Unexpected response from AICraft API (HTTP {resp.status_code}).")


def fetch_schema_catalog() -> tuple[int, dict[str, Any]]:
    resp = httpx.get("https://aicraft4injection.com/v1/schema", headers=_build_headers(""), timeout=30)
    return _parse_response(resp)


def post_first_shot(raw_credential: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    resp = httpx.post(
        "https://aicraft4injection.com/v1/first-shot",
        json=payload,
        headers=_build_headers(raw_credential, json_body=True),
        timeout=60,
    )
    return _parse_response(resp)


def post_optimize(raw_credential: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    resp = httpx.post(
        "https://aicraft4injection.com/v1/optimize",
        json=payload,
        headers=_build_headers(raw_credential, json_body=True),
        timeout=60,
    )
    return _parse_response(resp)


def _parse_response(resp: httpx.Response) -> tuple[int, dict[str, Any]]:
    try:
        data = resp.json()
        if not isinstance(data, dict):
            data = {"raw": data}
    except ValueError:
        data = {"status": 1, "code": f"HTTP_{resp.status_code}", "message": resp.text[:500]}
    return resp.status_code, data


def clean_num(val: Any) -> int | float | None:
    if val is None or val == "" or isinstance(val, bool):
        return None
    try:
        num = float(val)
        return int(num) if int(num) == num and abs(num) < 1e12 else num
    except (TypeError, ValueError):
        return None


def fmt_val(v: Any) -> str:
    if isinstance(v, float):
        return f"{int(v)}" if abs(v - round(v)) < 1e-6 else f"{round(v, 2)}"
    return str(v)


def _stage_idx(key: str, prefix: str) -> int | None:
    if key.startswith(prefix) and key[len(prefix):].isdigit():
        return int(key[len(prefix):])
    return None


def _extract_thinking(resp: dict[str, Any]) -> dict[str, Any]:
    diag = resp.get("diagnostics")
    if isinstance(diag, dict):
        oe = diag.get("optimize_export")
        if isinstance(oe, dict) and isinstance(oe.get("recommend_thinking"), dict):
            return oe["recommend_thinking"]
        if isinstance(diag.get("recommend_thinking"), dict):
            return diag["recommend_thinking"]
    return {}


def format_error_markdown(title: str, http_code: int, resp: dict[str, Any]) -> str:
    code = str(resp.get("code") or f"HTTP_{http_code}")
    msg = str(resp.get("message") or resp.get("msg") or resp.get("detail") or f"HTTP {http_code} error")
    rem = resp.get("quota_remaining")
    fields = resp.get("fields") if isinstance(resp.get("fields"), list) else []
    suggestions = resp.get("suggestions") if isinstance(resp.get("suggestions"), list) else []

    lines = [
        f"## {title} — Error (`{code}`)",
        "",
        f"- **Message:** {msg}",
    ]
    if isinstance(rem, (int, float)):
        lines.append(f"- **Quota Remaining:** {int(rem)} calls")
    if fields:
        lines.append(f"- **Fields:** `{', '.join(str(f) for f in fields)}`")
    if suggestions:
        lines.append(f"- **Valid Options:** {', '.join(str(s) for s in suggestions[:15])}")
    return "\n".join(lines)


def format_first_shot_markdown(resp: dict[str, Any], req: dict[str, Any], notes: list[str] | None = None) -> str:
    params = resp.get("parameters") if isinstance(resp.get("parameters"), list) else []
    flat = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    by_key = {str(p.get("key")): p for p in params if isinstance(p, dict) and p.get("key")}
    process_no = str(resp.get("process_no") or flat.get("process_no") or "")
    method = str(resp.get("method") or flat.get("method") or "profile")
    confidence = str(resp.get("confidence") or flat.get("confidence") or "medium")
    rem = resp.get("quota_remaining")
    p_unit = str(req.get("pressure_unit") or "MPa")

    thinking = _extract_thinking(resp)
    stability = thinking.get("stability") if isinstance(thinking.get("stability"), dict) else {}

    all_notes = list(notes or [])
    raw_summary = str(resp.get("summary") or "")
    if "WARNING:" in raw_summary:
        all_notes.append("WARNING: " + raw_summary.split("WARNING:", 1)[1].strip())

    lines = [
        "# Injection Molding First-Shot Setup Sheet",
        "",
        f"**Strategy:** `{method}` | **Confidence:** `{confidence}`"
        + (f" | **Archive ID (`process_no`):** `{process_no}`" if process_no else "")
        + (f" | **Quota Remaining:** `{int(rem)}`" if isinstance(rem, (int, float)) else ""),
        "",
    ]
    if all_notes:
        lines.append("### Engineering Notices")
        for n in all_notes:
            lines.append(f"- {n}")
        lines.append("")

    temp_keys = ["NT"] + sorted(
        [k for k in by_key if _stage_idx(k, "BT") is not None],
        key=lambda k: _stage_idx(k, "BT") or 0,
    ) + [k for k in ("mold_temp", "hot_runner_temperature") if k in by_key]
    if temp_keys:
        lines.extend(["### 1. Barrel & Mold Temperatures", "| Code | Parameter | Setpoint | Unit |", "|---|---|---:|---|"])
        for k in temp_keys:
            if k in by_key:
                r = by_key[k]
                lines.append(f"| `{k}` | {r.get('name', k)} | **{fmt_val(r.get('value'))}** | {r.get('unit') or 'C'} |")
        lines.append("")

    inj_indices = sorted({i for p in ("IP", "IV", "IL") for k in by_key for i in [_stage_idx(k, p)] if i is not None})
    if inj_indices:
        lines.extend([
            "### 2. Multi-Stage Filling Profile",
            f"| Stage | Velocity (`IV`, mm/s) | Pressure Limit (`IP`, {p_unit}) | Stroke End (`IL`, mm) |",
            "|---|---:|---:|---:|",
        ])
        for i in inj_indices:
            iv = fmt_val(by_key[f"IV{i}"]["value"]) if f"IV{i}" in by_key else "—"
            ip = fmt_val(by_key[f"IP{i}"]["value"]) if f"IP{i}" in by_key else "—"
            il = fmt_val(by_key[f"IL{i}"]["value"]) if f"IL{i}" in by_key else "—"
            lines.append(f"| Stage {i + 1} (`#{i}`) | **{iv}** | **{ip}** | **{il}** |")
        lines.append("")

    scalar_keys = [k for k in ("VPTL", "MEL", "ML0", "MSR0", "MBP0", "MP0", "DDAM", "PP0", "PT0", "IT", "CT") if k in by_key]
    if scalar_keys:
        lines.extend(["### 3. Switchover, Plasticizing, Packing & Timers", "| Code | Parameter | Setpoint | Unit |", "|---|---|---:|---|"])
        for k in scalar_keys:
            r = by_key[k]
            lines.append(f"| `{k}` | {r.get('name', k)} | **{fmt_val(r.get('value'))}** | {r.get('unit', '')} |")
        lines.append("")

    m_keys = stability.get("margin_keys") if isinstance(stability.get("margin_keys"), list) else []
    m_vals = stability.get("margin_headrooms") if isinstance(stability.get("margin_headrooms"), list) else []
    if m_keys and len(m_keys) == len(m_vals):
        badges = [f"`{k}`: {float(v) * 100:+.0f}%" for k, v in zip(m_keys, m_vals)]
        lines.extend([
            "### 4. Process Stability Window",
            f"- **Rating:** `{str(stability.get('level') or 'assessed').upper()}` | **Limiting:** `{stability.get('limiting') or 'none'}`",
            f"- **Headrooms:** {' · '.join(badges)}",
            "",
        ])

    if process_no:
        lines.append(f"> **Stored for Defect Tuning:** Pass `process_no` = `{process_no}` (or `business_id` = `{req.get('business_id', '')}`) to `optimize_defect` after your trial shot.")
    return "\n".join(lines)


def format_optimize_markdown(resp: dict[str, Any], req: dict[str, Any], notes: list[str] | None = None) -> str:
    params = resp.get("parameters") if isinstance(resp.get("parameters"), list) else []
    flat = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    by_key = {str(p.get("key")): p for p in params if isinstance(p, dict) and p.get("key")}
    process_no = str(resp.get("process_no") or flat.get("process_no") or req.get("process_no") or "")
    method = str(resp.get("method") or flat.get("method") or "fuzzy")
    rem = resp.get("quota_remaining")

    thinking = _extract_thinking(resp)
    raw_changes = thinking.get("param_changes") if isinstance(thinking.get("param_changes"), list) else []
    defects = req.get("defect_info") if isinstance(req.get("defect_info"), list) else []
    defect_badges = [f"`{d.get('desc')}` ({d.get('level')})" for d in defects if isinstance(d, dict) and d.get("desc")]

    lines = [
        "# Injection Molding Defect-Driven Tuning Sheet",
        "",
        f"**Defect(s):** {', '.join(defect_badges) or 'N/A'} | **Strategy:** `{method}`"
        + (f" | **Archive ID:** `{process_no}`" if process_no else "")
        + (f" | **Quota Remaining:** `{int(rem)}`" if isinstance(rem, (int, float)) else ""),
        "",
    ]

    all_notes = list(notes or [])
    resp_notes = resp.get("notes") if isinstance(resp.get("notes"), list) else []
    if "process_from_archive=true" in resp_notes and process_no:
        all_notes.insert(0, f"Loaded baseline process automatically from archive (`{process_no}`).")
    if all_notes:
        lines.append("### Tuning Context")
        for n in all_notes:
            lines.append(f"- {n}")
        lines.append("")

    deltas = []
    for ch in raw_changes:
        if not isinstance(ch, dict) or not ch.get("key"):
            continue
        k = str(ch["key"])
        b_v, a_v = ch.get("from"), ch.get("to")
        meta = by_key.get(k, {})
        if isinstance(b_v, (int, float)) and isinstance(a_v, (int, float)):
            diff = float(a_v) - float(b_v)
            if abs(diff) < 1e-6:
                continue
            sign = "+" if diff > 0 else ""
            deltas.append((k, meta.get("name", k), fmt_val(b_v), fmt_val(a_v), f"{sign}{fmt_val(diff)}", meta.get("unit", "")))

    if deltas:
        lines.extend([
            f"### 1. Recommended Parameter Adjustments ({len(deltas)} Changed)",
            "| Code | Parameter | Previous | Adjusted | Delta | Unit |",
            "|---|---|---:|---:|---:|---|",
        ])
        for k, name, b_t, a_t, d_t, unit in deltas:
            lines.append(f"| `{k}` | {name} | {b_t} | **{a_t}** | `{d_t}` | {unit} |")
        lines.append("")

    key_setpoints = [k for k in ("NT", "IV0", "IV1", "IV2", "IP0", "IP1", "IP2", "IL0", "IL1", "VPTL", "MEL", "ML0", "PP0", "PT0", "IT", "CT") if k in by_key]
    if key_setpoints:
        lines.extend(["### 2. Updated Key Machine Setpoints", "| Code | Parameter | Updated Value | Unit |", "|---|---|---:|---|"])
        for k in key_setpoints:
            r = by_key[k]
            lines.append(f"| `{k}` | {r.get('name', k)} | **{fmt_val(r.get('value'))}** | {r.get('unit', '')} |")
        lines.append("")

    return "\n".join(lines)

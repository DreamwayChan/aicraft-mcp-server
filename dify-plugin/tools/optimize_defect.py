from collections.abc import Generator
import json
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils.aicraft_api import (
    clean_num,
    format_error_markdown,
    format_optimize_markdown,
    post_optimize,
)


def _parse_current_params(raw_text: str) -> tuple[dict[str, Any], str | None]:
    text = raw_text.strip()
    if not text:
        return {}, None
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        return {}, f"Invalid `current_params_json`: {exc}"
    if isinstance(parsed, list):
        return {
            str(item["key"]): item["value"]
            for item in parsed
            if isinstance(item, dict) and item.get("key") and item.get("value") is not None
        }, None
    if isinstance(parsed, dict):
        if isinstance(parsed.get("data"), dict) and parsed["data"]:
            return dict(parsed["data"]), None
        return dict(parsed), None
    return {}, "`current_params_json` must be a JSON object or parameters array."


class OptimizeDefectTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        api_key = str(self.runtime.credentials.get("api_key") or "")

        defect_code = str(tool_parameters.get("defect_code") or "").strip()
        severity = str(tool_parameters.get("defect_severity") or "moderate").strip().lower()
        defects: list[dict[str, Any]] = [{"desc": defect_code, "level": severity}]

        fb = str(tool_parameters.get("previous_step_feedback") or "").strip().lower()
        if fb in ("good", "bad"):
            defects[0]["feedback"] = fb

        sec_code = str(tool_parameters.get("secondary_defect_code") or "").strip()
        sec_sev = str(tool_parameters.get("secondary_defect_severity") or "").strip().lower()
        if sec_code and sec_code.upper() != "NONE" and sec_sev in ("mild", "moderate", "severe", "critical"):
            defects.append({"desc": sec_code, "level": sec_sev})

        current_params, cp_err = _parse_current_params(str(tool_parameters.get("current_params_json") or ""))
        if cp_err:
            yield self.create_text_message(cp_err)
            return

        payload: dict[str, Any] = {
            "defect_info": defects,
            "trace": True,
        }
        job_id = str(tool_parameters.get("business_id") or "").strip()
        proc_no = str(tool_parameters.get("process_no") or "").strip()
        if job_id:
            payload["business_id"] = job_id
        if proc_no:
            payload["process_no"] = proc_no
        if current_params:
            payload["current_params"] = current_params

        for key in (
            "actual_mould_temp",
            "actual_injection_peak_pressure",
            "actual_fast_injection_speed",
            "min_buffer_position",
            "actual_vp_position",
            "actual_product_weight",
        ):
            val = clean_num(tool_parameters.get(key))
            if val is not None and val >= 0:
                payload[key] = val

        poly = str(tool_parameters.get("polymer_abbreviation") or "").strip().upper()
        if poly:
            payload["polymer_abbreviation"] = poly
        wall = clean_num(tool_parameters.get("product_ave_thickness"))
        if wall is not None and 0 < wall < 50:
            payload["product_ave_thickness"] = wall
            payload["mold"] = {"product_ave_thickness": wall}

        p_unit = str(tool_parameters.get("pressure_unit") or "MPa").strip()
        if p_unit in ("MPa", "bar"):
            payload["pressure_unit"] = p_unit

        http_code, resp = post_optimize(api_key, payload)
        if http_code != 200 or resp.get("status", 1) != 0:
            yield self.create_text_message(format_error_markdown("AICraft Defect Tuning", http_code, resp))
            yield self.create_json_message(resp)
            return

        md = format_optimize_markdown(resp, payload)
        yield self.create_text_message(md)
        yield self.create_json_message(
            {
                "status": "OK",
                "process_no": resp.get("process_no", proc_no),
                "quota_remaining": resp.get("quota_remaining"),
                "summary": resp.get("summary", ""),
                "parameters": resp.get("parameters", []),
                "data": resp.get("data", {}),
            }
        )

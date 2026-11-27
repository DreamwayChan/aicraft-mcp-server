from collections.abc import Generator
import json
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils.aicraft_api import (
    clean_num,
    format_error_markdown,
    format_first_shot_markdown,
    post_first_shot,
)


class FirstShotSetupTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        api_key = str(self.runtime.credentials.get("api_key") or "")

        notes: list[str] = []
        extra: dict[str, Any] = {}
        raw_extra = str(tool_parameters.get("extra_json") or "").strip()
        if raw_extra:
            try:
                parsed = json.loads(raw_extra)
                if isinstance(parsed, dict):
                    extra = parsed
            except ValueError as exc:
                yield self.create_text_message(f"Invalid `extra_json`: {exc}")
                return

        polymer = dict(extra.get("polymer")) if isinstance(extra.get("polymer"), dict) else {}
        polymer["polymer_abbreviation"] = str(tool_parameters.get("polymer_abbreviation") or "").strip().upper()
        grade = str(tool_parameters.get("polymer_trademark") or "").strip()
        if grade:
            polymer["polymer_trademark"] = grade
        for key in (
            "melt_density",
            "recommend_melt_temperature",
            "recommend_mold_temperature",
            "recommend_back_pressure",
        ):
            val = clean_num(tool_parameters.get(key))
            if val is not None and val > 0:
                polymer[key] = val

        mold = dict(extra.get("mold")) if isinstance(extra.get("mold"), dict) else {}
        wall = clean_num(tool_parameters.get("product_ave_thickness"))
        if wall is not None:
            mold["product_ave_thickness"] = wall
        for key in (
            "product_max_thickness",
            "projected_area_cm2",
            "single_cavity_part_weight_g",
            "gate_thickness",
        ):
            val = clean_num(tool_parameters.get(key))
            if val is not None and val > 0:
                mold[key] = val

        flow_l = clean_num(tool_parameters.get("product_max_length"))
        if flow_l is not None and flow_l > 0:
            mold["product_max_length"] = flow_l
            mold["flow_length"] = flow_l

        cav = clean_num(tool_parameters.get("cavity_num"))
        if cav is not None and cav >= 1:
            mold["cavity_num"] = int(round(float(cav)))

        runner_wt = clean_num(tool_parameters.get("runner_weight"))
        if runner_wt is not None and runner_wt >= 0:
            mold["runner_weight"] = runner_wt

        r_type = str(tool_parameters.get("runner_type") or "").strip().lower()
        if r_type in ("cold", "hot"):
            mold["runner_type"] = r_type

        injector: dict[str, Any] = {}
        if isinstance(extra.get("machine"), dict) and isinstance(extra["machine"].get("injector"), dict):
            injector.update(extra["machine"]["injector"])
        screw_d = clean_num(tool_parameters.get("injector_screw_diameter_mm"))
        if screw_d is not None:
            injector["injector_screw_diameter_mm"] = screw_d

        for key in (
            "injector_max_injection_stroke_mm",
            "injector_max_injection_velocity",
            "injector_max_injection_pressure",
        ):
            val = clean_num(tool_parameters.get(key))
            if val is not None and val > 0:
                injector[key] = val

        zones = clean_num(tool_parameters.get("machine_barrel_temperature_stage"))
        if zones is not None:
            z_int = int(round(float(zones)))
            if 1 <= z_int <= 12:
                injector["machine_barrel_temperature_stage"] = z_int
            elif z_int > 12:
                notes.append(
                    f"Ignored `machine_barrel_temperature_stage={z_int}` (expected zone count 4 or 5, not Celsius)."
                )

        machine = dict(extra.get("machine")) if isinstance(extra.get("machine"), dict) else {}
        clamp = clean_num(tool_parameters.get("machine_clamp_force_ton"))
        if clamp is not None and clamp > 0:
            machine["machine_clamp_force_ton"] = clamp
        drive = str(tool_parameters.get("power_method") or "").strip().lower()
        if drive in ("electric", "hydraulic"):
            machine["power_method"] = drive
        p_unit = str(tool_parameters.get("pressure_unit") or "MPa").strip()
        if p_unit in ("MPa", "bar"):
            machine["pressure_unit"] = p_unit
        machine["injector"] = injector

        payload = {k: v for k, v in extra.items() if k not in ("polymer", "mold", "machine")}
        payload["polymer"] = polymer
        payload["mold"] = mold
        payload["machine"] = machine
        payload["trace"] = True
        if p_unit in ("MPa", "bar"):
            payload["pressure_unit"] = p_unit

        job_id = str(tool_parameters.get("business_id") or "").strip()
        if job_id:
            payload["business_id"] = job_id

        shot_g = clean_num(tool_parameters.get("target_shot_weight_g"))
        if shot_g is not None and shot_g > 0:
            payload["target_shot_weight_g"] = shot_g
            mold.setdefault("product_total_weight", shot_g)

        http_code, resp = post_first_shot(api_key, payload)
        if http_code != 200 or resp.get("status", 1) != 0:
            yield self.create_text_message(format_error_markdown("AICraft First-Shot Setup", http_code, resp))
            yield self.create_json_message(resp)
            return

        md = format_first_shot_markdown(resp, payload, notes=notes)
        yield self.create_text_message(md)
        yield self.create_json_message(
            {
                "status": "OK",
                "process_no": resp.get("process_no", ""),
                "process_index_id": resp.get("process_index_id"),
                "quota_remaining": resp.get("quota_remaining"),
                "summary": resp.get("summary", ""),
                "parameters": resp.get("parameters", []),
                "data": resp.get("data", {}),
            }
        )

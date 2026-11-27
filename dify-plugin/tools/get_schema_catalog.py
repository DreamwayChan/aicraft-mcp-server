from collections.abc import Generator
import json
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils.aicraft_api import fetch_schema_catalog


class GetSchemaCatalogTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        del tool_parameters
        http_code, data = fetch_schema_catalog()
        if http_code != 200:
            yield self.create_text_message(f"Failed to fetch schema catalog (HTTP {http_code}): {json.dumps(data)}")
            yield self.create_json_message(data)
            return

        defects = data.get("defects") or []
        levels = (data.get("defect_levels") or {}).get("values") or []
        units = data.get("units") or {}
        summary = (
            "### AICraft Injection Molding Schema Catalog (Free)\n\n"
            f"- **Default Units:** `{json.dumps(units)}`\n"
            f"- **Defect Severity Levels:** `{', '.join(str(x) for x in levels)}` (or numeric `0..1`)\n"
            f"- **Supported Defect Codes ({len(defects)}):** `{', '.join(str(d) for d in defects)}`\n"
            f"- **Recommended Flow:** {data.get('flow', '')}\n"
        )
        yield self.create_text_message(summary)
        yield self.create_json_message(data)

from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from utils.aicraft_api import verify_credentials_zero_cost


class AicraftInjectionMoldingProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        raw_value = str(credentials.get("api_key") or "")
        try:
            verify_credentials_zero_cost(raw_value)
        except ValueError as exc:
            raise ToolProviderCredentialValidationError(str(exc)) from exc
        except Exception as exc:
            raise ToolProviderCredentialValidationError(f"Credential check failed: {exc}") from exc

import json
from pathlib import Path
from typing import Dict, Any, Optional
import httpx

from .base import BaseTool
from ...config.settings import get_settings


class CalendlyCreateTool(BaseTool):
    @property
    def name(self) -> str:
        return "create_calendly_event"

    @property
    def description(self) -> str:
        return "Crea un evento programado en Calendly (requiere event_type_uri, start/end e invitee)."

    async def execute(
        self,
        event_type_uri: str,
        invitee_email: str,
        invitee_name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        settings = get_settings()
        token_path = Path("credentials/calendly_token.json")
        if not token_path.exists():
            return self._error_response("No se encontró credentials/calendly_token.json; realiza OAuth primero.")
        try:
            token = json.loads(token_path.read_text())
            access_token = token.get("access_token")
            if not access_token:
                return self._error_response("El token de Calendly no contiene access_token.")

            payload = {
                "event_type": event_type_uri,
                "invitees": [
                    {
                        "email": invitee_email,
                        "name": invitee_name or invitee_email,
                    }
                ],
            }
            if start_time and end_time:
                payload["start_time"] = start_time
                payload["end_time"] = end_time

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post("https://api.calendly.com/scheduled_events", headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            return self._success_response({"event": data})
        except Exception as exc:
            return self._error_response(f"Error creando evento en Calendly: {exc}")


calendly_create_tool = CalendlyCreateTool()









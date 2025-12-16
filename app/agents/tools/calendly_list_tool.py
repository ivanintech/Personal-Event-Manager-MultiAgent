import json
import base64
import httpx
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

from .base import BaseTool
from ...config.settings import get_settings


class CalendlyListTool(BaseTool):
    @property
    def name(self) -> str:
        return "list_calendly_events"

    @property
    def description(self) -> str:
        return "Lista eventos próximos desde Calendly usando el token OAuth almacenado."

    async def execute(self, days_ahead: int = 30, max_results: int = 20, **kwargs) -> Dict[str, Any]:
        settings = get_settings()
        token_path = Path("credentials/calendly_token.json")
        if not token_path.exists():
            return self._error_response("No se encontró credentials/calendly_token.json; realiza OAuth primero.")
        try:
            token = json.loads(token_path.read_text())

            async def refresh_and_save():
                refresh_token = token.get("refresh_token")
                if not refresh_token:
                    return False
                basic = base64.b64encode(f"{settings.calendly_client_id}:{settings.calendly_client_secret}".encode()).decode()
                headers_r = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {basic}",
                }
                data_r = {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                }
                async with httpx.AsyncClient(timeout=20) as client:
                    resp_r = await client.post("https://auth.calendly.com/oauth/token", data=data_r, headers=headers_r)
                    resp_r.raise_for_status()
                    new_token = resp_r.json()
                token_path.write_text(json.dumps(new_token, indent=2))
                return new_token

            async def fetch(access_token: str, tok: Dict[str, Any]):
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }
                params = {
                    "min_start_time": datetime.now(timezone.utc).isoformat(),
                    "sort": "start_time:asc",
                    "count": max_results,
                }
                if tok.get("organization"):
                    params["organization"] = tok["organization"]
                if tok.get("owner"):
                    params["user"] = tok["owner"]
                url = "https://api.calendly.com/scheduled_events"
                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.get(url, headers=headers, params=params)
                    return resp

            access_token = token.get("access_token")
            if not access_token:
                return self._error_response("El token de Calendly no contiene access_token.")

            resp = await fetch(access_token, token)
            if resp.status_code == 401:
                new_token = await refresh_and_save()
                if not new_token:
                    return self._error_response("Token Calendly expirado y sin refresh_token.")
                access_token = new_token.get("access_token")
                if not access_token:
                    return self._error_response("Refresh Calendly sin access_token.")
                resp = await fetch(access_token, new_token)

            resp.raise_for_status()
            data = resp.json()
            events = data.get("collection", [])
            simplified = []
            for ev in events:
                simplified.append(
                    {
                        "uri": ev.get("uri"),
                        "name": ev.get("name"),
                        "status": ev.get("status"),
                        "start_time": ev.get("start_time"),
                        "end_time": ev.get("end_time"),
                        "created_at": ev.get("created_at"),
                        "invitee_counter": ev.get("invitee_counter"),
                    }
                )
            # Si no hay eventos agendados, intentar devolver event_types con sus links
            if simplified:
                return self._success_response({"events": simplified, "event_types": []})

            # Fallback: event_types (links para agendar)
            async with httpx.AsyncClient(timeout=20) as client:
                params_et = {}
                if token.get("organization"):
                    params_et["organization"] = token["organization"]
                if token.get("owner"):
                    params_et["user"] = token["owner"]
                resp_et = await client.get(
                    "https://api.calendly.com/event_types",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    params=params_et,
                )
                resp_et.raise_for_status()
                et_data = resp_et.json()
                et_collection = et_data.get("collection", [])
                event_types = []
                for et in et_collection:
                    event_types.append(
                        {
                            "uri": et.get("uri"),
                            "name": et.get("name"),
                            "scheduling_uri": et.get("scheduling_url") or et.get("scheduling_uri"),
                            "duration": et.get("duration"),
                            "pooling_type": et.get("pooling_type"),
                        }
                    )
            return self._success_response({"events": [], "event_types": event_types})
        except Exception as exc:
            return self._error_response(f"Error listando eventos de Calendly: {exc}")


calendly_list_tool = CalendlyListTool()


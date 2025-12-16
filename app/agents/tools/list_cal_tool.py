import logging
from typing import Dict, Any, Optional, List
import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
import zoneinfo

from .base import BaseTool
from ...config.settings import get_settings

logger = logging.getLogger(__name__)


class ListCalendarEventsTool(BaseTool):
    """
    Lista eventos confirmados en Google Calendar (ventana próxima, por defecto 14 días).
    """

    @property
    def name(self) -> str:
        return "list_cal_events"

    @property
    def description(self) -> str:
        return "Lista eventos confirmados en Google Calendar en la ventana próxima (default 14 días)."

    async def execute(self, days_ahead: int = 14, max_results: int = 10, **kwargs) -> Dict[str, Any]:
        settings = get_settings()
        try:
            creds = Credentials.from_authorized_user_file(
                settings.google_oauth_token_path,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            service = build('calendar', 'v3', credentials=creds)

            now = datetime.now(timezone.utc)
            time_min = now.isoformat()
            time_max = (now + timedelta(days=days_ahead)).isoformat()

            events_result = service.events().list(
                calendarId=settings.google_calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])

            formatted = []
            def fmt(dt_obj: Optional[datetime]) -> str:
                if not dt_obj:
                    return ""
                # conviértelo a tz del evento si viene en start/end
                return dt_obj.strftime("%Y-%m-%d %H:%M %Z")

            def parse_dt(dt_dict: Dict[str, Any]) -> Optional[datetime]:
                if not dt_dict:
                    return None
                dt_iso = dt_dict.get("dateTime") or dt_dict.get("date")
                tz = dt_dict.get("timeZone")
                if not dt_iso:
                    return None
                try:
                    if len(dt_iso) == 10:  # date only
                        dt_iso = dt_iso + "T00:00:00+00:00"
                    dt = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
                    if tz:
                        try:
                            dt = dt.astimezone(zoneinfo.ZoneInfo(tz))
                        except Exception:
                            pass
                    return dt
                except Exception:
                    return None

            for ev in events:
                start_dt = parse_dt(ev.get("start", {}))
                end_dt = parse_dt(ev.get("end", {}))
                formatted.append({
                    "id": ev.get("id"),
                    "summary": ev.get("summary"),
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                    "status": ev.get("status"),
                    "hangoutLink": ev.get("hangoutLink"),
                    "start_fmt": fmt(start_dt),
                    "end_fmt": fmt(end_dt),
                    "timezone": ev.get("start", {}).get("timeZone") or ev.get("end", {}).get("timeZone"),
                })

            return self._success_response({"events": formatted})
        except Exception as e:
            logger.error("Failed to list calendar events: %s", e, exc_info=True)
            # Fallback: devolver confirmados desde Supabase para no dejar al usuario sin respuesta
            try:
                base = settings.supabase_url.rstrip("/")
                key = settings.supabase_service_role_key
                headers = {
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                }
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.get(
                        f"{base}/rest/v1/extracted_events",
                        headers=headers,
                        params={"status": "eq.confirmed", "select": "*", "order": "start_at.asc", "limit": "10"},
                    )
                    r.raise_for_status()
                    rows = r.json()
                # formatear también en fallback
                formatted = []
                for ev in rows:
                    formatted.append({
                        "id": ev.get("id"),
                        "summary": ev.get("title") or "(sin título)",
                        "start": ev.get("start_at"),
                        "end": ev.get("end_at"),
                        "status": ev.get("status"),
                        "hangoutLink": ev.get("location"),
                        "start_fmt": ev.get("start_at"),
                        "end_fmt": ev.get("end_at"),
                        "timezone": ev.get("timezone"),
                    })
                return self._success_response({"events": formatted, "fallback": "supabase"})
            except Exception as e2:
                logger.error("Fallback Supabase failed: %s", e2, exc_info=True)
                return self._error_response(f"No se pudo listar eventos confirmados (Google ni Supabase): {e}")


list_cal_tool = ListCalendarEventsTool()


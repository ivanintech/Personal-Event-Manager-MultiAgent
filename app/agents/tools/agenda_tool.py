import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import zoneinfo
import httpx

from .base import BaseTool
from ...config.settings import get_settings

logger = logging.getLogger(__name__)


class AgendaListTool(BaseTool):
    """
    Lista citas/próximos eventos desde Supabase (extracted_events + calendar_events).
    Devuelve próximos eventos ordenados por start_at.
    """

    @property
    def name(self) -> str:
        return "list_agenda_events"

    @property
    def description(self) -> str:
        return "Lista las próximas citas importantes almacenadas en la agenda (Supabase)."

    async def execute(self, limit: int = 5, days_ahead: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        settings = get_settings()
        base = settings.supabase_url.rstrip("/")
        key = settings.supabase_service_role_key
        if not base or not key:
            return self._error_response("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")

        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        params_events = {
            "select": "*",
            "order": "start_at.asc",
            "limit": str(limit),
        }
        # Si se pide acotar en días, podríamos filtrar client-side; mantengo simple para no depender de RPC.

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r1 = await client.get(f"{base}/rest/v1/extracted_events", headers=headers, params=params_events)
                r1.raise_for_status()
                extracted = r1.json()

                r2 = await client.get(f"{base}/rest/v1/calendar_events", headers=headers, params=params_events)
                r2.raise_for_status()
                calendar = r2.json()

            text = self._format_events(extracted, calendar, limit)
            return self._success_response(
                {
                    "extracted_events": extracted,
                    "calendar_events": calendar,
                    "limit": limit,
                    "text": text,
                }
            )
        except Exception as e:
            logger.error("Failed to list agenda events: %s", e, exc_info=True)
            return self._error_response(f"No se pudo listar agenda: {e}")

    def _fmt_dt(self, iso_str: Optional[str], tz: Optional[str]) -> str:
        if not iso_str:
            return ""
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            if tz:
                try:
                    dt = dt.astimezone(zoneinfo.ZoneInfo(tz))
                except Exception:
                    pass
            return dt.strftime("%Y-%m-%d %H:%M %Z")
        except Exception:
            return iso_str

    def _format_events(self, extracted: List[Dict[str, Any]], calendar: List[Dict[str, Any]], limit: int) -> str:
        events = []
        # Index calendar events by (title, start) to evitar duplicados con extracted confirmados
        calendar_keys = set()
        for ev in calendar or []:
            events.append(
                {
                    "id": ev.get("id"),
                    "title": ev.get("title") or "(sin título)",
                    "start": self._fmt_dt(ev.get("start_at"), ev.get("timezone")),
                    "end": self._fmt_dt(ev.get("end_at"), ev.get("timezone")),
                    "status": ev.get("status") or "",
                    "source": ev.get("provider") or "calendar",
                    "location": ev.get("location") or "",
                    "attendees": ev.get("attendees"),
                }
            )
            calendar_keys.add(((ev.get("title") or "").strip().lower(), self._fmt_dt(ev.get("start_at"), ev.get("timezone"))))

        for ev in extracted or []:
            key = ((ev.get("title") or "").strip().lower(), self._fmt_dt(ev.get("start_at"), ev.get("timezone")))
            # si ya hay en calendar el mismo título+start y el extracted está confirmed, salta para evitar doble
            if key in calendar_keys and (ev.get("status") == "confirmed"):
                continue
            events.append(
                {
                    "id": ev.get("id"),
                    "title": ev.get("title") or "(sin título)",
                    "start": self._fmt_dt(ev.get("start_at"), ev.get("timezone")),
                    "end": self._fmt_dt(ev.get("end_at"), ev.get("timezone")),
                    "status": ev.get("status") or "",
                    "source": ev.get("source") or "extracted",
                    "location": ev.get("location") or "",
                    "attendees": ev.get("attendees"),
                    "confidence": ev.get("confidence"),
                }
            )
        if not events:
            return "No encontré próximas citas en la agenda."
        lines = ["Próximas citas importantes:"]
        for ev in sorted(events, key=lambda x: x.get("start") or "")[:limit]:
            lines.append(
                f"- id={ev.get('id')} | {ev['title']} | {ev.get('start')} - {ev.get('end')} | estado: {ev.get('status')} | fuente: {ev.get('source')}"
            )
        return "\n".join(lines)


agenda_list_tool = AgendaListTool()


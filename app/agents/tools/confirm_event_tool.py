import logging
from typing import Dict, Any, Optional
import httpx
from datetime import datetime, timedelta

from .base import BaseTool
from ...config.settings import get_settings
from .calendar_tool import calendar_tool

logger = logging.getLogger(__name__)


class ConfirmEventTool(BaseTool):
    """
    Confirma un extracted_event (proposed) creando el evento en Google Calendar
    y actualizando Supabase (extracted_events.status=confirmed, calendar_events insert).
    """

    @property
    def name(self) -> str:
        return "confirm_agenda_event"

    @property
    def description(self) -> str:
        return "Confirma una cita propuesta creando el evento en Google Calendar y actualizando Supabase."

    async def execute(self, event_id: int, **kwargs) -> Dict[str, Any]:
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

        try:
            # 1) Obtener el extracted_event
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(
                    f"{base}/rest/v1/extracted_events",
                    headers=headers,
                    params={"id": f"eq.{event_id}", "select": "*"},
                )
                r.raise_for_status()
                rows = r.json()
            if not rows:
                return self._error_response(f"No encontré extracted_event con id={event_id}")
            ev = rows[0]

            # Validar datos mínimos
            summary = ev.get("title") or "Evento"
            start_iso = ev.get("start_at")
            end_iso = ev.get("end_at")
            timezone = ev.get("timezone") or "UTC"
            attendees = ev.get("attendees") or []
            location = ev.get("location") or ""
            status = ev.get("status") or ""
            if status != "proposed":
                return self._error_response(f"El evento no está en estado proposed (actual: {status})")
            if not start_iso:
                return self._error_response("Falta start_at en el evento")
            if not end_iso:
                # si no hay end, asumir 1 hora
                start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                end_iso = (start_dt + timedelta(hours=1)).isoformat()

            # 2) Crear en Google Calendar
            cal_res = await calendar_tool.execute(
                summary=summary,
                start_datetime=start_iso,
                end_datetime=end_iso,
                description=ev.get("notes") or "",
                attendees=attendees if isinstance(attendees, list) else [],
                timezone=timezone,
                location=location,
            )
            if not cal_res.get("success"):
                return self._error_response(f"Calendar error: {cal_res.get('error')}")
            cal_data = cal_res.get("result") or {}
            provider_event_id = cal_data.get("event_id")
            provider_link = cal_data.get("event_link")

            # 3) Actualizar Supabase: extracted_events.status -> confirmed, calendar_events insert/update
            async with httpx.AsyncClient(timeout=30) as client:
                # update extracted_events
                r_upd = await client.patch(
                    f"{base}/rest/v1/extracted_events",
                    headers=headers,
                    params={"id": f"eq.{event_id}"},
                    json={"status": "confirmed"},
                )
                r_upd.raise_for_status()

                # upsert calendar_events
                cal_payload = {
                    "provider": "google",
                    "provider_event_id": provider_event_id,
                    "calendar_id": settings.google_calendar_id,
                    "title": summary,
                    "start_at": start_iso,
                    "end_at": end_iso,
                    "status": "confirmed",
                    "extra": {"link": provider_link},
                }
                r_cal = await client.post(
                    f"{base}/rest/v1/calendar_events",
                    headers=headers,
                    params={"on_conflict": "provider,provider_event_id"},
                    json=[cal_payload],
                )
                r_cal.raise_for_status()

            return self._success_response(
                {
                    "event_id": event_id,
                    "calendar_event_id": provider_event_id,
                    "calendar_link": provider_link,
                    "status": "confirmed",
                }
            )
        except Exception as e:
            logger.error("Failed to confirm agenda event: %s", e, exc_info=True)
            return self._error_response(f"No se pudo confirmar el evento: {e}")


confirm_event_tool = ConfirmEventTool()









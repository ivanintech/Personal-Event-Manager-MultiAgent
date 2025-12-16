import json
from datetime import datetime
from typing import Dict, Any
import httpx

from .base import BaseTool
from .calendly_list_tool import calendly_list_tool
from ...config.settings import get_settings


class CalendlyIngestTool(BaseTool):
    @property
    def name(self) -> str:
        return "ingest_calendly_events"

    @property
    def description(self) -> str:
        return "Ingesta eventos de Calendly a extracted_events en Supabase (source=calendly)."

    async def execute(self, max_results: int = 20, **kwargs) -> Dict[str, Any]:
        settings = get_settings()
        base = settings.supabase_url.rstrip("/")
        key = settings.supabase_service_role_key
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        }
        try:
            # Obtener eventos desde Calendly
            res = await calendly_list_tool.execute(max_results=max_results)
            if not res.get("success"):
                return res
            events = res["result"].get("events", [])
            rows = []
            for ev in events:
                start = ev.get("start_time")
                end = ev.get("end_time")
                title = ev.get("name") or "(sin título)"
                if not start or not end:
                    continue
                rows.append(
                    {
                        "message_id": None,
                        "title": title,
                        "start_at": start,
                        "end_at": end,
                        "timezone": None,
                        "location": None,
                        "attendees": json.dumps([]),
                        "status": "proposed",
                        "confidence": 0.6,
                        "calendar_refs": json.dumps([{"provider": "calendly", "event_uri": ev.get("uri")}]),
                        "notes": None,
                        "source": "calendly",
                    }
                )
            if not rows:
                return self._success_response({"inserted": 0, "events": []})

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(f"{base}/rest/v1/extracted_events", headers=headers, json=rows)
                resp.raise_for_status()
                inserted = resp.json()
            return self._success_response({"inserted": len(inserted), "events": inserted})
        except Exception as exc:
            return self._error_response(f"Error ingiriendo eventos de Calendly: {exc}")


calendly_ingest_tool = CalendlyIngestTool()









"""
CalendarAgent: Especializado en operaciones de calendario (listar, crear, actualizar eventos).
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ...config.settings import get_settings
from ...agents.tool_exec import execute_tool

logger = logging.getLogger(__name__)


class CalendarAgent:
    """Agente especializado en gestión de calendario."""

    def __init__(self):
        self.settings = get_settings()
        self.name = "CalendarAgent"

    async def list_events(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """
        Lista eventos del calendario.
        
        Args:
            start_date: Fecha inicio (ISO format)
            end_date: Fecha fin (ISO format)
            max_results: Máximo de resultados
            
        Returns:
            Dict con eventos encontrados
        """
        try:
            result = await execute_tool(
                "list_cal_events",
                start_date=start_date,
                end_date=end_date,
                max_results=max_results,
            )
            return result
        except Exception as e:
            logger.error(f"CalendarAgent.list_events error: {e}")
            return {"success": False, "error": str(e), "result": None}

    async def create_event(
        self,
        summary: str,
        start_datetime: str,
        end_datetime: str,
        attendees: List[str],
        timezone: str = "UTC",
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Crea un evento en el calendario.
        
        Args:
            summary: Título del evento
            start_datetime: Inicio (ISO format)
            end_datetime: Fin (ISO format)
            attendees: Lista de emails
            timezone: Zona horaria
            description: Descripción opcional
            
        Returns:
            Dict con resultado de la creación
        """
        try:
            result = await execute_tool(
                "create_calendar_event",
                summary=summary,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                attendees=attendees,
                timezone=timezone,
                description=description or "",
            )
            return result
        except Exception as e:
            logger.error(f"CalendarAgent.create_event error: {e}")
            return {"success": False, "error": str(e), "result": None}

    async def check_conflicts(
        self,
        start_datetime: str,
        end_datetime: str,
        timezone: str = "UTC",
    ) -> Dict[str, Any]:
        """
        Verifica conflictos en el calendario para un rango de tiempo.
        
        Args:
            start_datetime: Inicio (ISO format)
            end_datetime: Fin (ISO format)
            timezone: Zona horaria
            
        Returns:
            Dict con has_conflicts: bool y events: List
        """
        try:
            # Lista eventos en el rango
            events_result = await self.list_events(
                start_date=start_datetime,
                end_date=end_datetime,
            )
            
            if not events_result.get("success"):
                return {"has_conflicts": False, "events": [], "error": events_result.get("error")}
            
            events = events_result.get("result", {}).get("events", [])
            # Filtra eventos confirmados que se solapan
            conflicts = []
            for ev in events:
                if ev.get("status") == "confirmed":
                    conflicts.append(ev)
            
            return {
                "has_conflicts": len(conflicts) > 0,
                "events": conflicts,
                "count": len(conflicts),
            }
        except Exception as e:
            logger.error(f"CalendarAgent.check_conflicts error: {e}")
            return {"has_conflicts": False, "events": [], "error": str(e)}








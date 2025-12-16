"""
CommsAgent: Especializado en comunicaciones (WhatsApp, notificaciones).
"""

import logging
from typing import Dict, Any, List, Optional

from ...config.settings import get_settings
from ...agents.tool_exec import execute_tool

logger = logging.getLogger(__name__)


class CommsAgent:
    """Agente especializado en comunicaciones (WhatsApp, SMS, etc.)."""

    def __init__(self):
        self.settings = get_settings()
        self.name = "CommsAgent"

    async def send_whatsapp(
        self,
        to: str,
        message: str,
    ) -> Dict[str, Any]:
        """
        Envía un mensaje de WhatsApp vía MCP (Twilio).
        
        Args:
            to: Número de teléfono (formato: +1234567890)
            message: Mensaje a enviar
            
        Returns:
            Dict con resultado del envío
        """
        try:
            result = await execute_tool(
                "send_whatsapp",
                to=to,
                message=message,
            )
            return result
        except Exception as e:
            logger.error(f"CommsAgent.send_whatsapp error: {e}")
            return {"success": False, "error": str(e), "result": None}

    async def read_whatsapp_recent(
        self,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Lee mensajes recientes de WhatsApp (placeholder para futura implementación MCP).
        
        Args:
            limit: Número máximo de mensajes
            
        Returns:
            Dict con mensajes encontrados
        """
        try:
            result = await execute_tool(
                "read_whatsapp",
                limit=limit,
            )
            return result
        except Exception as e:
            logger.error(f"CommsAgent.read_whatsapp_recent error: {e}")
            return {"success": False, "error": str(e), "result": None}








"""
WhatsApp Tool: Envía mensajes de WhatsApp vía MCP (Twilio).
"""

import logging
from typing import Dict, Any, Optional

from .base import BaseTool
from ...mcp.clients.twilio_http import TwilioHttpMCPClient

logger = logging.getLogger(__name__)


class WhatsAppTool(BaseTool):
    """Tool para enviar mensajes de WhatsApp usando Twilio MCP."""

    def __init__(self):
        super().__init__()
        self.client: Optional[TwilioHttpMCPClient] = None
        self._init_client()

    def _init_client(self):
        """Inicializa cliente Twilio si hay credenciales."""
        try:
            self.client = TwilioHttpMCPClient()
            # Verificar si tiene credenciales
            if not self.client.account_sid or not self.client.auth_token:
                logger.warning("Twilio credentials not configured, WhatsApp tool will fail")
                self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Twilio client: {e}")
            self.client = None

    @property
    def name(self) -> str:
        return "send_whatsapp"

    @property
    def description(self) -> str:
        return (
            "Envía un mensaje de WhatsApp a un número de teléfono. "
            "Requiere: to (número con código país, ej: +1234567890), message (texto del mensaje)."
        )

    async def execute(
        self,
        to: str,
        message: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Envía mensaje WhatsApp.
        
        Args:
            to: Número de teléfono (formato: +1234567890)
            message: Mensaje a enviar
            
        Returns:
            Dict con success/result/error
        """
        if not to or not message:
            return self._error_response("Faltan parámetros 'to' o 'message'")

        if not self.client:
            return self._error_response(
                "Cliente Twilio no configurado. Configura TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM"
            )

        try:
            result = await self.client.execute("send_message", to=to, message=message)
            if result.get("success"):
                logger.info(f"WhatsApp sent: To='{to}', Message='{message[:50]}...'")
            return result
        except Exception as e:
            logger.error(f"Failed to send WhatsApp: {e}", exc_info=True)
            return self._error_response(f"Failed to send WhatsApp: {str(e)}")


# Instancia global
whatsapp_tool = WhatsAppTool()








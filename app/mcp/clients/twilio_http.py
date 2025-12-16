"""
Cliente MCP HTTP para WhatsApp usando Twilio API.
"""

import logging
from typing import Dict, Any, Optional
import httpx
import os

from .base import BaseMCPClient

logger = logging.getLogger(__name__)


class TwilioHttpMCPClient(BaseMCPClient):
    """
    Cliente MCP HTTP específico para Twilio WhatsApp.
    Implementa send_message y read_recent_messages.
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        whatsapp_from: Optional[str] = None,
    ):
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.whatsapp_from = whatsapp_from or os.getenv("TWILIO_WHATSAPP_FROM")
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"
        self.client = httpx.AsyncClient(
            timeout=30,
            auth=(self.account_sid, self.auth_token) if self.account_sid and self.auth_token else None,
        )

    async def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Ejecuta una tool de Twilio WhatsApp.
        
        Soporta:
        - send_message: Envía mensaje WhatsApp
        - read_recent_messages: Lee mensajes recientes (placeholder)
        """
        if not self.account_sid or not self.auth_token:
            return {
                "success": False,
                "result": None,
                "error": "Twilio credentials not configured (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)",
            }

        if tool_name == "send_message" or tool_name == "whatsapp.send_message":
            return await self._send_message(**kwargs)
        elif tool_name == "read_recent_messages" or tool_name == "whatsapp.read_recent_messages":
            return await self._read_recent_messages(**kwargs)
        else:
            return {
                "success": False,
                "result": None,
                "error": f"Unknown Twilio tool: {tool_name}",
            }

    async def _send_message(self, to: str, message: str, **kwargs) -> Dict[str, Any]:
        """Envía mensaje WhatsApp vía Twilio API."""
        if not self.whatsapp_from:
            return {
                "success": False,
                "result": None,
                "error": "TWILIO_WHATSAPP_FROM not configured",
            }

        try:
            # Twilio WhatsApp API endpoint
            url = f"{self.base_url}/Messages.json"
            payload = {
                "From": f"whatsapp:{self.whatsapp_from}",
                "To": f"whatsapp:{to}",
                "Body": message,
            }
            
            resp = await self.client.post(url, data=payload)
            resp.raise_for_status()
            data = resp.json()
            
            return {
                "success": True,
                "result": {
                    "sid": data.get("sid"),
                    "status": data.get("status"),
                    "to": data.get("to"),
                    "from": data.get("from"),
                },
                "error": None,
            }
        except httpx.HTTPError as e:
            logger.error(f"Twilio HTTP error: {e}")
            return {
                "success": False,
                "result": None,
                "error": f"Twilio API error: {str(e)}",
            }

    async def _read_recent_messages(self, limit: int = 10, **kwargs) -> Dict[str, Any]:
        """
        Lee mensajes recientes (placeholder).
        Twilio no tiene un endpoint directo para leer mensajes entrantes vía API REST.
        Esto requeriría webhooks o Twilio Conversations API.
        """
        logger.warning("read_recent_messages not fully implemented (requires webhooks)")
        return {
            "success": False,
            "result": None,
            "error": "read_recent_messages requires webhook setup or Twilio Conversations API",
        }








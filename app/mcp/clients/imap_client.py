"""
Cliente MCP para IMAP (Thunderbird, Outlook, Gmail IMAP, etc.).

Permite leer y buscar emails vía IMAP.
"""

import logging
import imaplib
import email
from email.header import decode_header
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from ..protocol import JSONRPCRequest, JSONRPCResponse, MCPProtocol
from .base import BaseMCPClient

logger = logging.getLogger(__name__)


class IMAPMCPClient(BaseMCPClient):
    """
    Cliente MCP para IMAP (leer/buscar emails).
    
    Implementación directa que no usa servidor MCP externo,
    pero mantiene compatibilidad con la interfaz BaseMCPClient.
    """

    def __init__(
        self,
        host: str,
        port: int = 993,
        user: str = "",
        password: str = "",
        use_ssl: bool = True,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_ssl = use_ssl
        self._connection: Optional[imaplib.IMAP4_SSL] = None

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Conecta al servidor IMAP (síncrono, se ejecuta en thread)."""
        if self._connection:
            try:
                self._connection.noop()
                return self._connection
            except:
                pass

        if self.use_ssl:
            self._connection = imaplib.IMAP4_SSL(self.host, self.port)
        else:
            self._connection = imaplib.IMAP4(self.host, self.port)
            if self.port == 993:
                self._connection.starttls()

        self._connection.login(self.user, self.password)
        logger.debug(f"IMAP conectado a {self.host}:{self.port}")
        return self._connection

    def _decode_header(self, header: bytes) -> str:
        """Decodifica headers de email."""
        decoded = decode_header(header)
        parts = []
        for part, encoding in decoded:
            if isinstance(part, bytes):
                if encoding:
                    parts.append(part.decode(encoding))
                else:
                    parts.append(part.decode("utf-8", errors="ignore"))
            else:
                parts.append(str(part))
        return " ".join(parts)

    def _parse_email(self, msg_data: bytes) -> Dict[str, Any]:
        """Parsea un email a dict."""
        msg = email.message_from_bytes(msg_data)
        
        subject = self._decode_header(msg.get("Subject", b""))
        from_addr = self._decode_header(msg.get("From", b""))
        to_addr = self._decode_header(msg.get("To", b""))
        date_str = msg.get("Date", "")
        
        # Parsear cuerpo
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
                    except:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
            except:
                body = str(msg.get_payload())

        return {
            "subject": subject,
            "from": from_addr,
            "to": to_addr,
            "date": date_str,
            "body": body[:1000],  # Limitar tamaño
            "content_type": msg.get_content_type(),
        }

    async def send_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Envía una petición JSON-RPC 2.0 (convierte a formato interno)."""
        # Para clientes directos, convertimos JSON-RPC a formato interno
        method = request.method
        params = request.params or {}
        
        # Extraer tool name y arguments
        if method == MCPProtocol.TOOLS_CALL:
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            
            # Ejecutar tool
            result = await self.execute(tool_name, **arguments)
            
            if result.get("success"):
                return JSONRPCResponse.success(request.id, result.get("result"))
            else:
                return JSONRPCResponse.error(
                    request.id,
                    code=-32603,
                    message=result.get("error", "Unknown error"),
                )
        else:
            return JSONRPCResponse.error(
                request.id,
                code=-32601,
                message=f"Method not supported: {method}",
            )

    async def initialize(self, protocol_version: str = "2024-11-05") -> Dict[str, Any]:
        """Inicializa la conexión MCP (no-op para cliente directo)."""
        return {
            "protocolVersion": protocol_version,
            "capabilities": {},
            "serverInfo": {"name": "IMAPMCPClient", "version": "1.0.0"},
        }

    async def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Ejecuta un tool IMAP (formato simplificado para compatibilidad)."""
        if tool_name == "imap.search_emails" or tool_name == "search_emails":
            return await self._search_emails(**kwargs)
        elif tool_name == "imap.read_email" or tool_name == "read_email":
            return await self._read_email(**kwargs)
        elif tool_name == "imap.list_folders" or tool_name == "list_folders":
            return await self._list_folders(**kwargs)
        else:
            return {
                "success": False,
                "result": None,
                "error": f"Tool {tool_name} no soportado por IMAPMCPClient",
            }

    async def _search_emails(
        self,
        query: str = "ALL",
        folder: str = "INBOX",
        max_results: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """Busca emails en una carpeta."""
        import asyncio
        try:
            # Ejecutar operaciones IMAP en thread (imaplib es síncrono)
            loop = asyncio.get_event_loop()
            conn = await loop.run_in_executor(None, self._connect)
            await loop.run_in_executor(None, conn.select, folder)

            # Construir criterio de búsqueda
            # query puede ser: "ALL", "UNSEEN", "FROM user@example.com", "SUBJECT texto", etc.
            status, message_ids = await loop.run_in_executor(None, conn.search, None, query)
            
            if status != "OK":
                return {
                    "success": False,
                    "result": None,
                    "error": f"Error en búsqueda IMAP: {message_ids}",
                }

            email_ids = message_ids[0].split()
            if not email_ids:
                return {
                    "success": True,
                    "result": {"emails": [], "count": 0},
                    "error": None,
                }

            # Limitar resultados
            email_ids = email_ids[-max_results:]  # Más recientes primero
            emails = []

            for email_id in email_ids:
                try:
                    status, msg_data = await loop.run_in_executor(None, conn.fetch, email_id, "(RFC822)")
                    if status == "OK" and msg_data[0]:
                        parsed = self._parse_email(msg_data[0][1])
                        parsed["id"] = email_id.decode() if isinstance(email_id, bytes) else str(email_id)
                        emails.append(parsed)
                except Exception as e:
                    logger.warning(f"Error parseando email {email_id}: {e}")
                    continue

            return {
                "success": True,
                "result": {"emails": emails, "count": len(emails)},
                "error": None,
            }
        except Exception as e:
            logger.error(f"Error en IMAP search: {e}", exc_info=True)
            return {
                "success": False,
                "result": None,
                "error": str(e),
            }

    async def _read_email(self, email_id: str, folder: str = "INBOX", **kwargs) -> Dict[str, Any]:
        """Lee un email específico."""
        import asyncio
        try:
            # Ejecutar operaciones IMAP en thread
            loop = asyncio.get_event_loop()
            conn = await loop.run_in_executor(None, self._connect)
            await loop.run_in_executor(None, conn.select, folder)

            email_id_bytes = email_id.encode() if isinstance(email_id, str) else email_id
            status, msg_data = await loop.run_in_executor(None, conn.fetch, email_id_bytes, "(RFC822)")
            
            if status != "OK" or not msg_data[0]:
                return {
                    "success": False,
                    "result": None,
                    "error": f"Email {email_id} no encontrado",
                }

            parsed = self._parse_email(msg_data[0][1])
            parsed["id"] = email_id

            return {
                "success": True,
                "result": parsed,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Error leyendo email {email_id}: {e}", exc_info=True)
            return {
                "success": False,
                "result": None,
                "error": str(e),
            }

    async def _list_folders(self, **kwargs) -> Dict[str, Any]:
        """Lista carpetas disponibles."""
        import asyncio
        try:
            # Ejecutar operaciones IMAP en thread
            loop = asyncio.get_event_loop()
            conn = await loop.run_in_executor(None, self._connect)
            status, folders = await loop.run_in_executor(None, conn.list)
            
            if status != "OK":
                return {
                    "success": False,
                    "result": None,
                    "error": f"Error listando carpetas: {folders}",
                }

            folder_list = []
            for folder in folders:
                folder_str = folder.decode() if isinstance(folder, bytes) else str(folder)
                # Parsear formato: '(\\HasNoChildren) "/" "INBOX"'
                parts = folder_str.split(' "/" ')
                if len(parts) == 2:
                    folder_name = parts[1].strip('"')
                    folder_list.append(folder_name)

            return {
                "success": True,
                "result": {"folders": folder_list},
                "error": None,
            }
        except Exception as e:
            logger.error(f"Error listando carpetas: {e}", exc_info=True)
            return {
                "success": False,
                "result": None,
                "error": str(e),
            }

    def __del__(self):
        """Cierra conexión al destruir."""
        if self._connection:
            try:
                self._connection.close()
                self._connection.logout()
            except:
                pass


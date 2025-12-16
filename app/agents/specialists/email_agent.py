"""
EmailAgent: Especializado en operaciones de email (enviar, leer, buscar).
"""

import logging
from typing import Dict, Any, List, Optional

from ...config.settings import get_settings
from ...agents.tool_exec import execute_tool

logger = logging.getLogger(__name__)


class EmailAgent:
    """Agente especializado en gestión de email."""

    def __init__(self):
        self.settings = get_settings()
        self.name = "EmailAgent"

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Envía un email.
        
        Args:
            to: Destinatario (email)
            subject: Asunto
            body: Cuerpo del mensaje
            cc: Copia (opcional)
            bcc: Copia oculta (opcional)
            
        Returns:
            Dict con resultado del envío
        """
        try:
            result = await execute_tool(
                "send_email",
                to=to,
                subject=subject,
                body=body,
            )
            return result
        except Exception as e:
            logger.error(f"EmailAgent.send_email error: {e}")
            return {"success": False, "error": str(e), "result": None}

    async def search_emails(
        self,
        query: str,
        folder: str = "INBOX",
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """
        Busca emails vía IMAP o Gmail API.
        
        Args:
            query: Consulta de búsqueda (IMAP: 'ALL', 'UNSEEN', 'FROM user@example.com', 'SUBJECT texto', etc.)
            folder: Carpeta IMAP (default: 'INBOX')
            max_results: Máximo de resultados
            
        Returns:
            Dict con emails encontrados
        """
        try:
            result = await execute_tool(
                "search_emails",
                query=query,
                folder=folder,
                max_results=max_results,
            )
            return result
        except Exception as e:
            logger.error(f"EmailAgent.search_emails error: {e}")
            return {"success": False, "error": str(e), "result": None}

    async def read_email(
        self,
        email_id: str,
        folder: str = "INBOX",
    ) -> Dict[str, Any]:
        """
        Lee un email específico vía IMAP o Gmail API.
        
        Args:
            email_id: ID del email
            folder: Carpeta IMAP (default: 'INBOX')
            
        Returns:
            Dict con contenido del email
        """
        try:
            result = await execute_tool(
                "read_email",
                email_id=email_id,
                folder=folder,
            )
            return result
        except Exception as e:
            logger.error(f"EmailAgent.read_email error: {e}")
            return {"success": False, "error": str(e), "result": None}


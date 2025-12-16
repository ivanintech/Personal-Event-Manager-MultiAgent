"""
Tool para leer un email específico vía IMAP.
"""

import logging
from typing import Dict, Any, Optional

from .base import BaseTool
from ...config.settings import get_settings
from ...mcp.manager import get_mcp_manager

logger = logging.getLogger(__name__)
settings = get_settings()


class IMAPReadTool(BaseTool):
    """Tool para leer un email específico vía IMAP."""

    name: str = "read_email"
    description: str = (
        "Lee un email específico vía IMAP. "
        "Parámetros: 'email_id' (ID del email), 'folder' (carpeta, default: 'INBOX')."
    )

    async def execute(
        self,
        email_id: str,
        folder: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Lee un email específico."""
        if not email_id:
            return self._error_response("Falta 'email_id' para leer email.")

        folder = folder or "INBOX"

        try:
            # Llamar directamente al cliente MCP sin pasar por execute_tool para evitar recursión
            # Usar el manager MCP global que ya está inicializado
            from ...mcp.manager import get_mcp_manager
            from ...mcp.config import load_mcp_servers
            from pathlib import Path
            
            mcp_manager = get_mcp_manager(settings)
            
            # Cargar configuración de servidores (solo una vez, podría cachearse)
            BASE_DIR = Path(__file__).resolve().parent.parent.parent
            DEFAULT_MCP_CFG = BASE_DIR / "mcp" / "mcp_servers.json"
            servers_cfg = load_mcp_servers(settings.mcp_config_path or str(DEFAULT_MCP_CFG))
            
            # Buscar configuración del servidor IMAP
            server_config = None
            for server in servers_cfg:
                if server.get("name") == "imap":
                    server_config = server
                    break
            
            # Obtener cliente MCP directamente
            mcp_client = await mcp_manager.get_client(
                server_name="imap",
                server_config=server_config,
                tool_name="read_email",
            )
            
            if mcp_client:
                # Ejecutar directamente sin pasar por execute_tool
                res = await mcp_client.execute("read_email", email_id=email_id, folder=folder)
                if res.get("success"):
                    logger.info(f"Email {email_id} leído exitosamente")
                    return self._success_response(res.get("result"))
                else:
                    logger.error(f"Error leyendo email {email_id}: {res.get('error')}")
                    return self._error_response(res.get("error") or "Error desconocido leyendo email.")
            else:
                # Si no hay cliente MCP, devolver error informativo
                return self._error_response("Cliente IMAP MCP no disponible. Verifica la configuración de IMAP en mcp_servers.json.")
        except Exception as e:
            # Evitar recursión en el logging - no usar exc_info=True si hay problemas
            error_msg = str(e)
            logger.error(f"Excepción leyendo email: {error_msg}")
            return self._error_response(f"Excepción leyendo email: {error_msg}")


imap_read_tool = IMAPReadTool()




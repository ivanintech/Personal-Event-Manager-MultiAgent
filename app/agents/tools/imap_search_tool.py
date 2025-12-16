"""
Tool para buscar emails vía IMAP.
"""

import logging
from typing import Dict, Any, Optional

from .base import BaseTool
from ...config.settings import get_settings
from ...mcp.manager import get_mcp_manager

logger = logging.getLogger(__name__)
settings = get_settings()


class IMAPSearchTool(BaseTool):
    """Tool para buscar emails vía IMAP."""

    name: str = "search_emails"
    description: str = (
        "Busca emails vía IMAP. "
        "Parámetros: 'query' (criterio IMAP: 'ALL', 'UNSEEN', 'FROM user@example.com', 'SUBJECT texto', etc.), "
        "'folder' (carpeta, default: 'INBOX'), 'max_results' (default: 10)."
    )

    async def execute(
        self,
        query: str = "ALL",
        folder: Optional[str] = None,
        max_results: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """Busca emails vía IMAP."""
        if not query:
            return self._error_response("Falta 'query' para buscar emails.")

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
                tool_name="search_emails",
            )
            
            if mcp_client:
                # Ejecutar directamente sin pasar por execute_tool
                res = await mcp_client.execute("search_emails", query=query, folder=folder, max_results=max_results)
                if res.get("success"):
                    logger.info(f"IMAP search exitoso: {res.get('result', {}).get('count', 0)} emails")
                    return self._success_response(res.get("result"))
                else:
                    logger.error(f"Error en IMAP search: {res.get('error')}")
                    return self._error_response(res.get("error") or "Error desconocido en búsqueda IMAP.")
            else:
                # Si no hay cliente MCP, devolver error informativo
                return self._error_response("Cliente IMAP MCP no disponible. Verifica la configuración de IMAP en mcp_servers.json.")
        except Exception as e:
            # Evitar recursión en el logging - no usar exc_info=True si hay problemas
            error_msg = str(e)
            logger.error(f"Excepción en IMAP search: {error_msg}")
            return self._error_response(f"Excepción en búsqueda IMAP: {error_msg}")


imap_search_tool = IMAPSearchTool()




"""
Puente de ejecución de tools: puede usar MCP (mock o real) o el registry local.

Ahora usa el protocolo MCP estándar (JSON-RPC 2.0) y MCPClientManager para gestión.
"""

import logging
from typing import Any, Dict, Optional
from pathlib import Path

from ..config.settings import get_settings
from ..mcp.manager import get_mcp_manager
from ..mcp.adapters import to_mcp_call
from ..mcp.config import load_mcp_servers
from .tools import tool_registry

logger = logging.getLogger(__name__)
settings = get_settings()

# Rutas por defecto si no se pasan por env
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MCP_CFG = BASE_DIR / "mcp" / "mcp_servers.json"
DEFAULT_MCP_MAPPING = BASE_DIR / "mcp" / "mapping.json"

# Cargar configuración de servidores
servers_cfg = load_mcp_servers(settings.mcp_config_path or str(DEFAULT_MCP_CFG))

# Inicializar manager MCP
_mcp_manager = get_mcp_manager(settings)
_mcp_manager.set_servers_config(servers_cfg)


async def execute_tool(tool_name: str, **kwargs) -> Dict[str, Any]:
    """
    Ejecuta una tool usando protocolo MCP estándar (JSON-RPC 2.0):
    - Si USE_MOCK_MCP: pasa por cliente MCP mock (útil para pruebas).
    - Si no: intenta MCP real (IMAP directo, HTTP, SSE, stdio) o registry local.
    """
    # Primero intenta MCP (mock o real), luego fallback a registry local
    call = to_mcp_call(tool_name, kwargs)
    use_mcp = settings.use_mock_mcp or bool(servers_cfg)

    if use_mcp:
        # Buscar configuración del servidor
        server_config = None
        if servers_cfg:
            for server in servers_cfg:
                if server.get("name") == call.target.server:
                    server_config = server
                    break

        # Obtener cliente MCP apropiado usando el manager
        mcp_client = await _mcp_manager.get_client(
            server_name=call.target.server,
            server_config=server_config,
            tool_name=tool_name,
        )

        if mcp_client:
            client_type = "mock" if settings.use_mock_mcp else type(mcp_client).__name__
            logger.info(
                "Ejecutando vía MCP (%s): %s.%s",
                client_type,
                call.target.server,
                call.target.tool,
            )
            
            # Log detallado de MCP para el modo desarrollador
            # Nota: No tenemos acceso directo al log_callback aquí, pero podemos loguear
            logger.debug(f"🔌 MCP Protocol: JSON-RPC 2.0")
            logger.debug(f"📡 MCP Server: {call.target.server}")
            logger.debug(f"🔧 MCP Tool: {call.target.tool}")
            logger.debug(f"📦 MCP Client Type: {client_type}")

            # Usar método execute (compatibilidad) que internamente usa JSON-RPC 2.0
            try:
                res = await mcp_client.execute(
                    call.target.tool,  # Solo el nombre del tool, no server.tool
                    **call.arguments
                )
                # Si MCP falló, hacemos fallback local
                if res.get("success"):
                    logger.debug(f"✅ MCP execution successful via {client_type}")
                    return res
                logger.warning("Fallo MCP, fallback local: %s", res.get("error"))
            except Exception as e:
                logger.error(f"Error ejecutando tool MCP: {e}", exc_info=True)
                # Fallback a registry local

    logger.info("Ejecutando tool local (registry): %s", tool_name)
    return await tool_registry.execute_tool(tool_name, **kwargs)


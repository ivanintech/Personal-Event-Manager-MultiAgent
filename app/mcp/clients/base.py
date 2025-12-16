from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging

from ..protocol import JSONRPCRequest, JSONRPCResponse, MCPProtocol

logger = logging.getLogger(__name__)


class BaseMCPClient(ABC):
    """Interfaz base para clientes MCP (stdio/HTTP/SSE) usando JSON-RPC 2.0."""

    @abstractmethod
    async def send_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Envía una petición JSON-RPC 2.0 y devuelve la respuesta."""
        raise NotImplementedError

    @abstractmethod
    async def initialize(self, protocol_version: str = "2024-11-05") -> Dict[str, Any]:
        """Inicializa la conexión MCP."""
        raise NotImplementedError

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Lista herramientas disponibles."""
        request = MCPProtocol.create_tools_list_request()
        response = await self.send_request(request)
        if response._error:
            raise RuntimeError(f"Error listing tools: {response._error}")
        return response.result.get("tools", [])

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Llama a una herramienta MCP."""
        request = MCPProtocol.create_tools_call_request(tool_name, arguments)
        response = await self.send_request(request)
        if response._error:
            error_code = response._error.get("code", -32603)
            error_message = response._error.get("message", "Unknown error")
            error_data = response._error.get("data")
            raise RuntimeError(f"MCP Tool Error ({error_code}): {error_message} - {error_data}")
        return response.result

    # Método de compatibilidad hacia atrás
    async def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Ejecuta una tool MCP (método de compatibilidad).
        Devuelve dict con success/result/error para compatibilidad.
        """
        try:
            result = await self.call_tool(tool_name, kwargs)
            return {
                "success": True,
                "result": result,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {
                "success": False,
                "result": None,
                "error": str(e),
            }


class MockMCPClient(BaseMCPClient):
    """Cliente MCP simulado para desarrollo inicial."""

    async def send_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Envía una petición JSON-RPC 2.0 (mock)."""
        logger.info("MCP mock ejecutando %s con %s", request.method, request.params)
        return JSONRPCResponse.success(
            request.id,
            {"echo": {"method": request.method, "params": request.params}},
        )

    async def initialize(self, protocol_version: str = "2024-11-05") -> Dict[str, Any]:
        """Inicializa la conexión MCP (mock)."""
        return {
            "protocolVersion": protocol_version,
            "capabilities": {},
            "serverInfo": {"name": "MockMCPClient", "version": "1.0.0"},
        }

    async def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Ejecuta una tool (método de compatibilidad)."""
        logger.info("MCP mock ejecutando %s con %s", tool_name, list(kwargs.keys()))
        return {
            "success": True,
            "result": {"echo": {"tool": tool_name, "args": kwargs}},
            "error": None,
        }


def get_mcp_client(
    use_mock: bool = True,
    servers: Optional[List[Dict[str, Any]]] = None,
    tool_name: Optional[str] = None,
    server_config: Optional[Dict[str, Any]] = None,
) -> BaseMCPClient:
    """
    Crea un cliente MCP según la configuración.
    
    Args:
        use_mock: Si True, devuelve MockMCPClient
        servers: Lista de configuraciones de servidores (legacy)
        tool_name: Nombre del tool (para seleccionar cliente específico)
        server_config: Configuración de un servidor específico
        
    Returns:
        Cliente MCP apropiado (Mock, Stdio, HTTP, SSE, o cliente directo)
    """
    if use_mock:
        return MockMCPClient()

    # Si es un tool IMAP, usar cliente IMAP directo (compatibilidad)
    if tool_name and ("imap" in tool_name.lower() or "search_emails" in tool_name or "read_email" in tool_name):
        from ..config.settings import get_settings
        from .imap_client import IMAPMCPClient
        
        settings = get_settings()
        if settings.imap_host and settings.imap_user and settings.imap_pass:
            return IMAPMCPClient(
                host=settings.imap_host,
                port=settings.imap_port,
                user=settings.imap_user,
                password=settings.imap_pass,
                use_ssl=settings.imap_use_ssl,
            )
        logger.warning("IMAP config incompleta, usando fallback")

    # Usar server_config si está disponible
    config = server_config or {}
    
    # Determinar transporte
    transport = config.get("transport", "http")
    
    if transport == "stdio":
        from .stdio_client import StdioMCPClient
        command = config.get("command", "")
        args = config.get("args", [])
        env = config.get("env", {})
        if not command:
            raise ValueError("stdio transport requires 'command' in server config")
        return StdioMCPClient(command=command, args=args, env=env)
    
    elif transport == "sse" or transport == "http+sse":
        from .sse_client import SSEMCPClient
        base_url = config.get("base_url")
        if not base_url:
            raise ValueError("SSE transport requires 'base_url' in server config")
        return SSEMCPClient(base_url=base_url)
    
    else:  # http (default)
        from .http import HttpMCPClient
        base_url = config.get("base_url")
        if base_url:
            return HttpMCPClient(servers=[], base_url=base_url)
        # Fallback a lista de servidores (legacy)
        return HttpMCPClient(servers or [])


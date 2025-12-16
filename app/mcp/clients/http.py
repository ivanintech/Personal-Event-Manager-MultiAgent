"""
MCP Client using HTTP transport (JSON-RPC 2.0 over HTTP POST).

For MCP servers that expose HTTP endpoints.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from ..protocol import JSONRPCRequest, JSONRPCResponse, MCPProtocol
from .base import BaseMCPClient

logger = logging.getLogger(__name__)


class HttpMCPClient(BaseMCPClient):
    """
    Cliente MCP sobre HTTP usando JSON-RPC 2.0.
    
    Envía peticiones JSON-RPC 2.0 a endpoints HTTP.
    """

    def __init__(self, servers: List[Dict[str, Any]], base_url: Optional[str] = None):
        """
        Inicializa cliente HTTP MCP.
        
        Args:
            servers: Lista de configuraciones de servidores (para compatibilidad)
            base_url: URL base del servidor MCP (si se especifica, se usa directamente)
        """
        self.servers = {s["name"]: s for s in servers or []} if not base_url else {}
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self._initialized = False

    async def send_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Envía una petición JSON-RPC 2.0 vía HTTP POST."""
        url = self.base_url or self._get_base_url()
        if not url:
            raise RuntimeError("No base_url configured for HTTP MCP client")

        try:
            resp = await self.client.post(
                url,
                json=request.to_dict(),
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            # Asegurar que la respuesta sea un dict válido
            if not isinstance(data, dict):
                raise ValueError(f"Invalid response type: {type(data)}")
            return JSONRPCResponse.from_dict(data)
        except httpx.HTTPError as e:
            logger.error(f"HTTP MCP error: {e}")
            return JSONRPCResponse.error(
                request.id,
                code=-32603,
                message=f"HTTP error: {str(e)}",
            )

    def _get_base_url(self) -> Optional[str]:
        """Obtiene la URL base del primer servidor configurado."""
        if self.servers:
            first_server = next(iter(self.servers.values()))
            return first_server.get("base_url")
        return None

    async def initialize(self, protocol_version: str = "2024-11-05") -> Dict[str, Any]:
        """Inicializa la conexión MCP."""
        if self._initialized:
            return {"protocolVersion": protocol_version}

        request = MCPProtocol.create_initialize_request(protocol_version)
        response = await self.send_request(request)

        if response._error:
            raise RuntimeError(f"MCP Initialize error: {response._error}")

        # Enviar notificación initialized
        notification = MCPProtocol.create_initialized_notification()
        url = self.base_url or self._get_base_url()
        if url:
            try:
                await self.client.post(
                    url,
                    json=notification,
                    headers={"Content-Type": "application/json"},
                )
            except Exception as e:
                logger.warning(f"Error sending initialized notification: {e}")

        self._initialized = True
        return response.result

    async def close(self):
        """Cierra el cliente HTTP."""
        await self.client.aclose()




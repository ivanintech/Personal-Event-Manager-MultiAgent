"""
MCP Client using HTTP+SSE transport (JSON-RPC 2.0 over HTTP POST + Server-Sent Events).

For MCP servers that support HTTP with Server-Sent Events for bidirectional communication.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

import httpx

from ..protocol import JSONRPCRequest, JSONRPCResponse, parse_jsonrpc_message, MCPProtocol
from .base import BaseMCPClient

logger = logging.getLogger(__name__)


class SSEMCPClient(BaseMCPClient):
    """
    Cliente MCP usando HTTP+SSE (JSON-RPC 2.0).
    
    Usa HTTP POST para enviar requests y SSE para recibir responses.
    """

    def __init__(self, base_url: str):
        """
        Inicializa cliente SSE MCP.
        
        Args:
            base_url: URL base del servidor MCP (ej: "http://localhost:8000/mcp")
        """
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self._initialized = False
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._sse_task: Optional[asyncio.Task] = None

    async def _start_sse_listener(self):
        """Inicia el listener SSE para recibir mensajes."""
        if self._sse_task and not self._sse_task.done():
            return

        sse_url = f"{self.base_url}/sse"
        self._sse_task = asyncio.create_task(self._listen_sse(sse_url))

    async def _listen_sse(self, url: str):
        """Escucha eventos SSE y procesa mensajes JSON-RPC."""
        try:
            async with self.client.stream("GET", url) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    # Parsear evento SSE
                    if line.startswith("data: "):
                        data = line[6:]  # Remover "data: " prefix
                        try:
                            message = parse_jsonrpc_message(data)
                            if isinstance(message, JSONRPCResponse):
                                await self._handle_response(message)
                        except Exception as e:
                            logger.error(f"Error parsing SSE message: {e} - {data}")

        except Exception as e:
            logger.error(f"Error in SSE listener: {e}")
            # Reintentar después de un delay
            await asyncio.sleep(1)
            if not self._sse_task.done():
                await self._start_sse_listener()

    async def _handle_response(self, response: JSONRPCResponse):
        """Maneja una respuesta JSON-RPC recibida por SSE."""
        if response.id and str(response.id) in self._pending_requests:
            future = self._pending_requests.pop(str(response.id))
            if not future.done():
                future.set_result(response)
        else:
            logger.warning(f"Received response for unknown request ID: {response.id}")

    async def send_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Envía una petición JSON-RPC 2.0 vía HTTP POST."""
        await self._start_sse_listener()

        # Crear future para la respuesta
        future = asyncio.Future()
        self._pending_requests[str(request.id)] = future

        # Enviar request vía HTTP POST
        post_url = f"{self.base_url}/message"
        try:
            resp = await self.client.post(
                post_url,
                json=request.to_dict(),
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            self._pending_requests.pop(str(request.id), None)
            logger.error(f"HTTP error sending request: {e}")
            return JSONRPCResponse.error(
                request.id,
                code=-32603,
                message=f"HTTP error: {str(e)}",
            )

        # Esperar respuesta vía SSE (timeout de 30 segundos)
        try:
            response = await asyncio.wait_for(future, timeout=30.0)
            return response
        except asyncio.TimeoutError:
            self._pending_requests.pop(str(request.id), None)
            return JSONRPCResponse.error(
                request.id,
                code=-32603,
                message=f"Timeout waiting for response",
            )

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
        try:
            await self.client.post(
                f"{self.base_url}/message",
                json=notification,
                headers={"Content-Type": "application/json"},
            )
        except Exception as e:
            logger.warning(f"Error sending initialized notification: {e}")

        self._initialized = True
        return response.result

    async def close(self):
        """Cierra el cliente SSE."""
        if self._sse_task and not self._sse_task.done():
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass

        await self.client.aclose()


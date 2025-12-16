"""
MCP Client using stdio transport (JSON-RPC 2.0 over stdin/stdout).

For local MCP servers that communicate via standard input/output.
"""

import asyncio
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional

from ..protocol import JSONRPCRequest, JSONRPCResponse, parse_jsonrpc_message, MCPProtocol
from .base import BaseMCPClient

logger = logging.getLogger(__name__)


class StdioMCPClient(BaseMCPClient):
    """Cliente MCP usando transporte stdio (JSON-RPC 2.0)."""

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ):
        """
        Inicializa cliente stdio MCP.
        
        Args:
            command: Comando a ejecutar (ej: "node", "python")
            args: Argumentos del comando (ej: ["./server.js"])
            env: Variables de entorno adicionales
        """
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.process: Optional[subprocess.Popen] = None
        self._initialized = False
        self._request_id_counter = 0
        self._pending_requests: Dict[str, asyncio.Future] = {}

    async def _start_process(self):
        """Inicia el proceso del servidor MCP."""
        if self.process is not None:
            return

        # Preparar entorno
        import os
        full_env = os.environ.copy()
        full_env.update(self.env)

        # Iniciar proceso
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
            bufsize=0,  # Sin buffering para lectura inmediata
        )

        # Iniciar tarea de lectura (en background)
        self._read_task = asyncio.create_task(self._read_stdout())

        logger.info(f"Started MCP server process: {self.command} {' '.join(self.args)}")

    async def _read_stdout(self):
        """Lee mensajes JSON-RPC del stdout del proceso (newline-delimited JSON)."""
        if not self.process or not self.process.stdout:
            return

        while True:
            try:
                # Leer línea por línea (newline-delimited JSON)
                # process.stdout es StreamReader, readline() es async
                line_bytes = await self.process.stdout.readline()
                if not line_bytes:
                    # EOF - proceso terminó
                    break

                line = line_bytes.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                try:
                    message = parse_jsonrpc_message(line)
                    if isinstance(message, JSONRPCResponse):
                        await self._handle_response(message)
                    # Ignorar otros tipos de mensajes (notifications, etc.)
                except Exception as e:
                    logger.error(f"Error parsing JSON-RPC message: {e} - {line[:100]}")

            except asyncio.CancelledError:
                logger.info("Stdout reader cancelled")
                break
            except Exception as e:
                logger.error(f"Error reading stdout: {e}")
                break

    async def _handle_response(self, response: JSONRPCResponse):
        """Maneja una respuesta JSON-RPC."""
        if response.id and str(response.id) in self._pending_requests:
            future = self._pending_requests.pop(str(response.id))
            future.set_result(response)
        else:
            logger.warning(f"Received response for unknown request ID: {response.id}")

    async def send_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Envía una petición JSON-RPC 2.0."""
        await self._start_process()

        if not self.process or not self.process.stdin:
            raise RuntimeError("MCP server process not running")

        # Crear future para la respuesta
        future = asyncio.Future()
        self._pending_requests[str(request.id)] = future

        # Enviar request (newline-delimited JSON)
        request_json = request.to_json() + "\n"
        try:
            # Escribir a stdin del proceso
            self.process.stdin.write(request_json.encode("utf-8"))
            await self.process.stdin.drain()
            logger.debug(f"Sent request {request.id}: {request.method}")
        except Exception as e:
            self._pending_requests.pop(str(request.id), None)
            raise RuntimeError(f"Error sending request: {e}")

        # Esperar respuesta (timeout de 30 segundos)
        try:
            response = await asyncio.wait_for(future, timeout=30.0)
            return response
        except asyncio.TimeoutError:
            self._pending_requests.pop(str(request.id), None)
            raise RuntimeError(f"Timeout waiting for response to request {request.id}")

    async def initialize(self, protocol_version: str = "2024-11-05") -> Dict[str, Any]:
        """Inicializa la conexión MCP."""
        if self._initialized:
            return {"protocolVersion": protocol_version}

        from ..protocol import MCPProtocol

        request = MCPProtocol.create_initialize_request(protocol_version)
        response = await self.send_request(request)

        if response._error:
            raise RuntimeError(f"MCP Initialize error: {response._error}")

        # Enviar notificación initialized
        notification = MCPProtocol.create_initialized_notification()
        if self.process and self.process.stdin:
            notification_json = json.dumps(notification) + "\n"
            self.process.stdin.write(notification_json.encode("utf-8"))
            await self.process.stdin.drain()

        self._initialized = True
        return response.result

    async def close(self):
        """Cierra la conexión y termina el proceso."""
        # Cancelar tarea de lectura
        if hasattr(self, "_read_task") and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        
        if self.process:
            try:
                # Cerrar stdin para que el proceso termine
                if self.process.stdin:
                    self.process.stdin.close()
                    await self.process.stdin.wait_closed()
                
                # Esperar a que termine (con timeout)
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    # Forzar terminación si no termina
                    self.process.terminate()
                    await self.process.wait()
            except Exception as e:
                logger.error(f"Error closing process: {e}")
            finally:
                self.process = None
                self._initialized = False

    def __del__(self):
        """Cleanup al destruir."""
        if self.process:
            try:
                self.process.terminate()
            except:
                pass


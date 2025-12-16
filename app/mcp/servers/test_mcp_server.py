"""
Servidor MCP de prueba usando protocolo estándar (JSON-RPC 2.0).

Este servidor puede ejecutarse como:
- stdio: python test_mcp_server.py (para Cursor/Claude Desktop)
- HTTP: uvicorn test_mcp_server:app (para HTTP transport)
"""

import asyncio
import json
import sys
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# Importar protocolo MCP
try:
    from ..protocol import (
        JSONRPCRequest,
        JSONRPCResponse,
        JSONRPCNotification,
        parse_jsonrpc_message,
        MCPProtocol,
        JSONRPCErrorCode,
    )
except ImportError:
    # Fallback para cuando se ejecuta directamente o con uvicorn
    import sys
    from pathlib import Path
    root_dir = Path(__file__).parent.parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    from app.mcp.protocol import (
        JSONRPCRequest,
        JSONRPCResponse,
        JSONRPCNotification,
        parse_jsonrpc_message,
        MCPProtocol,
        JSONRPCErrorCode,
    )

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)

# Estado del servidor
_server_state = {
    "initialized": False,
    "protocol_version": "2024-11-05",
    "tools": [
        {
            "name": "test_echo",
            "description": "Echo tool que devuelve los argumentos recibidos",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Mensaje a hacer echo"},
                    "repeat": {"type": "integer", "description": "Número de repeticiones", "default": 1},
                },
                "required": ["message"],
            },
        },
        {
            "name": "test_add",
            "description": "Suma dos números",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "Primer número"},
                    "b": {"type": "number", "description": "Segundo número"},
                },
                "required": ["a", "b"],
            },
        },
        {
            "name": "test_get_time",
            "description": "Obtiene la hora actual",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
    ],
}

# Cola para respuestas SSE
_sse_responses: Dict[str, JSONRPCResponse] = {}


async def handle_initialize(request: JSONRPCRequest) -> JSONRPCResponse:
    """Maneja petición initialize."""
    params = request.params or {}
    protocol_version = params.get("protocolVersion", "2024-11-05")
    
    _server_state["initialized"] = True
    _server_state["protocol_version"] = protocol_version
    
    result = {
        "protocolVersion": protocol_version,
        "capabilities": {
            "tools": {},
            "resources": {},
            "prompts": {},
        },
        "serverInfo": {
            "name": "test-mcp-server",
            "version": "1.0.0",
        },
    }
    
    logger.info(f"Server initialized with protocol version {protocol_version}")
    return JSONRPCResponse.success(request.id, result)


async def handle_tools_list(request: JSONRPCRequest) -> JSONRPCResponse:
    """Maneja petición tools/list."""
    if not _server_state["initialized"]:
        return JSONRPCResponse.error(
            request.id,
            code=JSONRPCErrorCode.INVALID_REQUEST,
            message="Server not initialized. Call initialize first.",
        )
    
    result = {"tools": _server_state["tools"]}
    return JSONRPCResponse.success(request.id, result)


async def handle_tools_call(request: JSONRPCRequest) -> JSONRPCResponse:
    """Maneja petición tools/call."""
    if not _server_state["initialized"]:
        return JSONRPCResponse.error(
            request.id,
            code=JSONRPCErrorCode.INVALID_REQUEST,
            message="Server not initialized. Call initialize first.",
        )
    
    params = request.params or {}
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    if not tool_name:
        return JSONRPCResponse.error(
            request.id,
            code=JSONRPCErrorCode.INVALID_PARAMS,
            message="Missing 'name' parameter",
        )
    
    # Ejecutar tool
    if tool_name == "test_echo":
        message = arguments.get("message", "")
        repeat = arguments.get("repeat", 1)
        result = {
            "content": [
                {
                    "type": "text",
                    "text": (message + " ") * repeat,
                }
            ],
        }
        return JSONRPCResponse.success(request.id, result)
    
    elif tool_name == "test_add":
        a = arguments.get("a")
        b = arguments.get("b")
        if a is None or b is None:
            return JSONRPCResponse.error(
                request.id,
                code=JSONRPCErrorCode.INVALID_PARAMS,
                message="Missing 'a' or 'b' parameter",
            )
        result = {
            "content": [
                {
                    "type": "text",
                    "text": f"{a} + {b} = {a + b}",
                }
            ],
        }
        return JSONRPCResponse.success(request.id, result)
    
    elif tool_name == "test_get_time":
        now = datetime.now().isoformat()
        result = {
            "content": [
                {
                    "type": "text",
                    "text": f"Current time: {now}",
                }
            ],
        }
        return JSONRPCResponse.success(request.id, result)
    
    else:
        return JSONRPCResponse.error(
            request.id,
            code=JSONRPCErrorCode.METHOD_NOT_FOUND,
            message=f"Tool '{tool_name}' not found",
        )


async def handle_request(request: JSONRPCRequest) -> JSONRPCResponse:
    """Maneja una petición JSON-RPC."""
    method = request.method
    
    if method == MCPProtocol.INITIALIZE:
        return await handle_initialize(request)
    elif method == MCPProtocol.TOOLS_LIST:
        return await handle_tools_list(request)
    elif method == MCPProtocol.TOOLS_CALL:
        return await handle_tools_call(request)
    else:
        return JSONRPCResponse.error(
            request.id,
            code=JSONRPCErrorCode.METHOD_NOT_FOUND,
            message=f"Method '{method}' not found",
        )


# ============================================================================
# Modo stdio (para Cursor/Claude Desktop)
# ============================================================================

async def stdio_main():
    """Modo stdio: lee de stdin, escribe a stdout."""
    logger.info("Starting MCP server in stdio mode...")
    
    while True:
        try:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue
            
            try:
                message = parse_jsonrpc_message(line)
                if isinstance(message, JSONRPCRequest):
                    response = await handle_request(message)
                    print(response.to_json(), flush=True)
                elif isinstance(message, JSONRPCNotification):
                    # Notificaciones no requieren respuesta
                    if message.method == MCPProtocol.INITIALIZED:
                        logger.info("Received initialized notification")
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                error_response = JSONRPCResponse.error(
                    None,
                    code=JSONRPCErrorCode.PARSE_ERROR,
                    message=f"Error: {str(e)}",
                )
                print(error_response.to_json(), flush=True)
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")


# ============================================================================
# Modo HTTP (para HTTP transport)
# ============================================================================

if FASTAPI_AVAILABLE:
    app = FastAPI(title="Test MCP Server")
else:
    app = None


async def _handle_http_request(request: Request, use_sse: bool = False):
    """Maneja una petición HTTP JSON-RPC."""
    try:
        body = await request.json()
        message = parse_jsonrpc_message(body)
        
        if isinstance(message, JSONRPCRequest):
            response = await handle_request(message)
            
            # Si es request a /message, almacenar respuesta para SSE
            if use_sse and message.id:
                _sse_responses[str(message.id)] = response
                # Devolver respuesta vacía (la respuesta real va por SSE)
                return JSONResponse(content={})
            
            return JSONResponse(content=response.to_dict())
        elif isinstance(message, JSONRPCNotification):
            # Notificaciones no requieren respuesta
            if message.method == MCPProtocol.INITIALIZED:
                logger.info("Received initialized notification")
            return JSONResponse(content={})
        else:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid message type"},
            )
    except Exception as e:
        logger.error(f"Error processing HTTP request: {e}", exc_info=True)
        error_response = JSONRPCResponse.error(
            None,
            code=JSONRPCErrorCode.INTERNAL_ERROR,
            message=str(e),
        )
        return JSONResponse(
            status_code=500,
            content=error_response.to_dict(),
        )


if app:
    @app.post("/")
    async def http_endpoint(request: Request):
        """Endpoint HTTP para peticiones JSON-RPC."""
        return await _handle_http_request(request)
    
    @app.post("/message")
    async def message_endpoint(request: Request):
        """Endpoint HTTP para peticiones JSON-RPC (alias para SSE)."""
        return await _handle_http_request(request, use_sse=True)

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok", "initialized": _server_state["initialized"]}
    
    @app.get("/sse")
    async def sse_endpoint(request: Request):
        """Endpoint SSE para recibir respuestas JSON-RPC."""
        from fastapi.responses import StreamingResponse
        
        async def event_generator():
            """Genera eventos SSE."""
            # Mantener conexión viva y enviar respuestas cuando estén disponibles
            last_check = time.time()
            while True:
                # Verificar si hay respuestas pendientes
                current_time = time.time()
                if current_time - last_check > 0.1:  # Verificar cada 100ms
                    # Enviar todas las respuestas pendientes
                    for req_id, response in list(_sse_responses.items()):
                        try:
                            response_dict = response.to_dict()
                            yield f"data: {json.dumps(response_dict)}\n\n"
                            del _sse_responses[req_id]
                        except Exception as e:
                            logger.error(f"Error sending SSE response: {e}")
                    last_check = current_time
                
                # Mantener conexión viva con ping ocasional
                await asyncio.sleep(0.1)
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )


if __name__ == "__main__":
    # Determinar modo según argumentos
    if len(sys.argv) > 1 and sys.argv[1] == "http":
        if not FASTAPI_AVAILABLE:
            print("Error: FastAPI not available. Install with: pip install fastapi uvicorn", file=sys.stderr)
            sys.exit(1)
        import uvicorn
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001
        logger.info(f"Starting MCP server in HTTP mode on port {port}...")
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        # Modo stdio por defecto
        asyncio.run(stdio_main())


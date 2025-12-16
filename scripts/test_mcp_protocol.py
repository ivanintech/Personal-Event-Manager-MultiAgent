"""
Script para probar el protocolo MCP estándar.

Prueba la conexión con un servidor MCP y ejecuta algunas herramientas.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.mcp.clients.stdio_client import StdioMCPClient
from app.mcp.clients.http import HttpMCPClient
from app.mcp.clients.sse_client import SSEMCPClient
from app.mcp.protocol import MCPProtocol

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_stdio_client():
    """Prueba cliente stdio MCP."""
    logger.info("=" * 60)
    logger.info("Testing StdioMCPClient")
    logger.info("=" * 60)
    
    # Crear cliente stdio
    client = StdioMCPClient(
        command="python",
        args=[
            str(Path(__file__).parent.parent / "app" / "mcp" / "servers" / "test_mcp_server.py")
        ],
    )
    
    try:
        # Inicializar
        logger.info("1. Initializing MCP connection...")
        init_result = await client.initialize()
        logger.info(f"   ✓ Initialized: {init_result}")
        
        # Listar tools
        logger.info("2. Listing available tools...")
        tools = await client.list_tools()
        logger.info(f"   ✓ Found {len(tools)} tools:")
        for tool in tools:
            logger.info(f"     - {tool['name']}: {tool['description']}")
        
        # Llamar tool test_echo
        logger.info("3. Calling test_echo tool...")
        result = await client.call_tool("test_echo", arguments={"message": "Hello MCP!", "repeat": 3})
        logger.info(f"   ✓ Result: {result}")
        
        # Llamar tool test_add
        logger.info("4. Calling test_add tool...")
        result = await client.call_tool("test_add", arguments={"a": 42, "b": 58})
        logger.info(f"   ✓ Result: {result}")
        
        # Llamar tool test_get_time
        logger.info("5. Calling test_get_time tool...")
        result = await client.call_tool("test_get_time", arguments={})
        logger.info(f"   ✓ Result: {result}")
        
        logger.info("=" * 60)
        logger.info("✓ All tests passed!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"✗ Error: {e}", exc_info=True)
    finally:
        await client.close()


async def test_http_client():
    """Prueba cliente HTTP MCP."""
    logger.info("=" * 60)
    logger.info("Testing HttpMCPClient")
    logger.info("=" * 60)
    
    # Crear cliente HTTP
    client = HttpMCPClient(servers=[], base_url="http://localhost:8001")
    
    try:
        # Inicializar
        logger.info("1. Initializing MCP connection...")
        init_result = await client.initialize()
        logger.info(f"   ✓ Initialized: {init_result}")
        
        # Listar tools
        logger.info("2. Listing available tools...")
        tools = await client.list_tools()
        logger.info(f"   ✓ Found {len(tools)} tools:")
        for tool in tools:
            logger.info(f"     - {tool['name']}: {tool['description']}")
        
        # Llamar tool test_echo
        logger.info("3. Calling test_echo tool...")
        result = await client.call_tool("test_echo", arguments={"message": "Hello HTTP MCP!", "repeat": 2})
        logger.info(f"   ✓ Result: {result}")
        
        logger.info("=" * 60)
        logger.info("✓ All HTTP tests passed!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"✗ Error: {e}", exc_info=True)
        logger.info("Note: Make sure the HTTP MCP server is running:")
        logger.info("  python app/mcp/servers/test_mcp_server.py http 8001")
    finally:
        await client.close()


async def test_sse_client():
    """Prueba el cliente SSE MCP."""
    logger.info("=" * 60)
    logger.info("Testing SSEMCPClient")
    logger.info("=" * 60)
    
    client = SSEMCPClient(base_url="http://localhost:8001")
    
    try:
        # Inicializar
        logger.info("1. Initializing MCP connection...")
        init_result = await client.initialize()
        logger.info(f"   ✓ Initialized: {init_result}")
        
        # Listar tools
        logger.info("2. Listing available tools...")
        tools = await client.list_tools()
        logger.info(f"   ✓ Found {len(tools)} tools:")
        for tool in tools:
            logger.info(f"     - {tool['name']}: {tool['description']}")
        
        # Llamar tool test_echo
        logger.info("3. Calling test_echo tool...")
        result = await client.call_tool("test_echo", arguments={"message": "Hello SSE MCP!", "repeat": 2})
        logger.info(f"   ✓ Result: {result}")
        
        logger.info("=" * 60)
        logger.info("✓ All SSE tests passed!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"✗ Error: {e}", exc_info=True)
        logger.info("Note: Make sure the HTTP MCP server is running with SSE support:")
        logger.info("  python app/mcp/servers/test_mcp_server.py http 8001")
    finally:
        await client.close()


async def main():
    """Ejecuta todas las pruebas."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test MCP Protocol")
    parser.add_argument("--mode", choices=["stdio", "http", "sse", "all"], default="stdio", help="Test mode")
    args = parser.parse_args()
    
    if args.mode == "stdio" or args.mode == "all":
        await test_stdio_client()
    
    if args.mode == "http" or args.mode == "all":
        await test_http_client()
    
    if args.mode == "sse" or args.mode == "all":
        await test_sse_client()


if __name__ == "__main__":
    asyncio.run(main())


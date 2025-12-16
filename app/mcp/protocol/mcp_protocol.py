"""
Model Context Protocol (MCP) Standard Protocol Implementation.

Based on MCP Specification: https://modelcontextprotocol.io
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from .jsonrpc import JSONRPCRequest, JSONRPCResponse, JSONRPCErrorCode


@dataclass
class MCPTool:
    """MCP Tool Definition."""
    name: str
    description: str
    inputSchema: Dict[str, Any]  # JSON Schema


@dataclass
class MCPResource:
    """MCP Resource Definition."""
    uri: str
    name: str
    description: Optional[str] = None
    mimeType: Optional[str] = None


@dataclass
class MCPPrompt:
    """MCP Prompt Definition."""
    name: str
    description: Optional[str] = None
    arguments: Optional[List[Dict[str, Any]]] = None


@dataclass
class MCPInitializeParams:
    """MCP Initialize Request Parameters."""
    protocolVersion: str
    capabilities: Dict[str, Any] = field(default_factory=dict)
    clientInfo: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPInitializeResult:
    """MCP Initialize Response Result."""
    protocolVersion: str
    capabilities: Dict[str, Any] = field(default_factory=dict)
    serverInfo: Dict[str, Any] = field(default_factory=dict)


class MCPProtocol:
    """MCP Protocol Handler."""

    # Standard MCP Methods
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"

    @staticmethod
    def create_initialize_request(
        protocol_version: str = "2024-11-05",
        capabilities: Optional[Dict[str, Any]] = None,
        client_info: Optional[Dict[str, Any]] = None,
    ) -> JSONRPCRequest:
        """Create initialize request."""
        params = {
            "protocolVersion": protocol_version,
            "capabilities": capabilities or {},
            "clientInfo": client_info or {"name": "personal-coordination-agent", "version": "1.0.0"},
        }
        return JSONRPCRequest(method=MCPProtocol.INITIALIZE, params=params)

    @staticmethod
    def create_tools_list_request() -> JSONRPCRequest:
        """Create tools/list request."""
        return JSONRPCRequest(method=MCPProtocol.TOOLS_LIST)

    @staticmethod
    def create_tools_call_request(
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> JSONRPCRequest:
        """Create tools/call request."""
        params = {
            "name": tool_name,
            "arguments": arguments,
        }
        return JSONRPCRequest(method=MCPProtocol.TOOLS_CALL, params=params)

    @staticmethod
    def create_resources_list_request() -> JSONRPCRequest:
        """Create resources/list request."""
        return JSONRPCRequest(method=MCPProtocol.RESOURCES_LIST)

    @staticmethod
    def create_resources_read_request(uri: str) -> JSONRPCRequest:
        """Create resources/read request."""
        params = {"uri": uri}
        return JSONRPCRequest(method=MCPProtocol.RESOURCES_READ, params=params)

    @staticmethod
    def create_prompts_list_request() -> JSONRPCRequest:
        """Create prompts/list request."""
        return JSONRPCRequest(method=MCPProtocol.PROMPTS_LIST)

    @staticmethod
    def create_initialized_notification() -> Dict[str, Any]:
        """Create initialized notification (no response expected)."""
        return {
            "jsonrpc": "2.0",
            "method": MCPProtocol.INITIALIZED,
        }

    @staticmethod
    def parse_tools_list_response(response: JSONRPCResponse) -> List[MCPTool]:
        """Parse tools/list response."""
        if response.error:
            raise ValueError(f"MCP Error: {response.error}")
        
        tools_data = response.result.get("tools", [])
        return [MCPTool(**tool) for tool in tools_data]

    @staticmethod
    def parse_tools_call_response(response: JSONRPCResponse) -> Dict[str, Any]:
        """Parse tools/call response."""
        if response.error:
            error_code = response.error.get("code", JSONRPCErrorCode.INTERNAL_ERROR)
            error_message = response.error.get("message", "Unknown error")
            error_data = response.error.get("data")
            raise RuntimeError(f"MCP Tool Error ({error_code}): {error_message} - {error_data}")
        
        return response.result








from dataclasses import dataclass
from typing import Dict, Any

from pathlib import Path
from .mapping import load_tool_mapping
from ..config.settings import get_settings


@dataclass
class MCPTarget:
    """Identifica servidor y tool MCP."""

    server: str
    tool: str


@dataclass
class MCPCall:
    """Llamada MCP normalizada."""

    target: MCPTarget
    arguments: Dict[str, Any]


def to_mcp_call(tool_name: str, arguments: Dict[str, Any]) -> MCPCall:
    """
    Mapea nombre de tool del agente a server.tool.
    1) Busca en mapping (si existe)
    2) Si no, intenta parsear tool_name como server.tool
    3) Fallback: server=mock
    """
    settings = get_settings()
    default_mapping_path = (
        Path(__file__).resolve().parent / "mapping.json"
        if not settings.mcp_mapping_path or settings.mcp_mapping_path == "app/mcp/mapping.json"
        else settings.mcp_mapping_path
    )
    mapping = load_tool_mapping(str(default_mapping_path) if default_mapping_path else None)

    mapped = mapping.get(tool_name)
    if mapped:
        parts = mapped.split(".", 1)
    else:
        parts = tool_name.split(".", 1)

    if len(parts) == 2:
        server, tool = parts
    else:
        server, tool = "mock", parts[0]
    return MCPCall(target=MCPTarget(server=server, tool=tool), arguments=arguments)


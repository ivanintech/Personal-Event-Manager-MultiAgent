import json
from pathlib import Path
from typing import List, Dict, Any

DEFAULT_MCP_SERVERS = [
    {
        "name": "mock",
        "transport": "mock",
        "base_url": "http://localhost:9999",  # no se usa en mock
        "tools": ["calendar.list_events", "email.search"],
    }
]


def load_mcp_servers(path: str | None) -> List[Dict[str, Any]]:
    """
    Carga definición de MCP servers desde JSON.
    Acepta formatos:
      - lista de servidores
      - {"servers": [...]}
      - {"mcpServers": {...}} (forma de vite/desktop), se normaliza a lista
    Si no existe o falla la lectura, devuelve un mock por defecto.
    """
    if not path:
        return DEFAULT_MCP_SERVERS

    cfg_path = Path(path)
    if not cfg_path.exists():
        return DEFAULT_MCP_SERVERS

    try:
        with cfg_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if "servers" in data and isinstance(data["servers"], list):
                return data["servers"]
            if "mcpServers" in data and isinstance(data["mcpServers"], dict):
                servers = []
                for name, cfg in data["mcpServers"].items():
                    if isinstance(cfg, dict):
                        cfg_norm = {"name": name, **cfg}
                        servers.append(cfg_norm)
                if servers:
                    return servers
    except Exception:
        return DEFAULT_MCP_SERVERS

    return DEFAULT_MCP_SERVERS


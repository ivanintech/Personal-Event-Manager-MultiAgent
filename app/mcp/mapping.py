import json
from pathlib import Path
from typing import Dict


DEFAULT_MAPPING: Dict[str, str] = {}


def load_tool_mapping(path: str | None) -> Dict[str, str]:
    """
    Carga un mapping tool_name -> "server.tool".
    Si no existe, devuelve {} y se usará fallback (server mock).
    """
    if not path:
        return DEFAULT_MAPPING
    p = Path(path)
    if not p.exists():
        return DEFAULT_MAPPING
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return DEFAULT_MAPPING
    return DEFAULT_MAPPING










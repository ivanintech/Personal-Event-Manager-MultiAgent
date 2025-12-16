"""
Configuración compartida para tests.
"""

import pytest
import os
from fastapi.testclient import TestClient

# Configurar variables de entorno para tests
os.environ.setdefault("USE_MOCK_MCP", "true")
os.environ.setdefault("LANGGRAPH_AGENT", "false")  # Usar orchestrator simple para tests
os.environ.setdefault("EXECUTE_TOOLS_IN_GRAPH", "false")


@pytest.fixture
def client():
    """Cliente HTTP para tests."""
    from main import app
    return TestClient(app)


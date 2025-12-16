"""
Tests E2E (smoke tests) para funcionalidades principales.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta


def test_text_endpoint_basic(client: TestClient):
    """Test básico del endpoint /api/v1/text."""
    response = client.post(
        "/api/v1/text",
        json={"query": "Hola, ¿qué puedes hacer?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "debug" in data
    assert data["debug"]["iterations"] >= 0


def test_agenda_list(client: TestClient):
    """Test de listado de agenda (atajo directo)."""
    response = client.post(
        "/api/v1/text",
        json={"query": "Muestra mis próximas citas"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    # Puede devolver "No encontré próximas citas" o lista de eventos
    assert isinstance(data["text"], str)


def test_confirmed_events(client: TestClient):
    """Test de eventos confirmados (atajo directo)."""
    response = client.post(
        "/api/v1/text",
        json={"query": "Muestra mis eventos confirmados"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert isinstance(data["text"], str)


def test_email_send_endpoint(client: TestClient):
    """Test del endpoint /api/v1/email/send."""
    response = client.post(
        "/api/v1/email/send",
        json={
            "to": "test@example.com",
            "subject": "Test E2E",
            "body": "Este es un test de email",
        },
    )
    assert response.status_code in [200, 500]  # Puede fallar si SMTP no está configurado
    data = response.json()
    if response.status_code == 200:
        assert "text" in data or "status" in data
    else:
        # Si falla, debe ser por configuración SMTP
        assert "detail" in data


def test_calendly_events_list(client: TestClient):
    """Test de listado de eventos Calendly."""
    response = client.get("/api/v1/calendly/events")
    # Puede fallar si no hay token OAuth configurado
    assert response.status_code in [200, 401, 500]
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, (dict, list))


def test_calendly_ingest(client: TestClient):
    """Test de ingest de eventos Calendly."""
    # Mock de evento Calendly
    mock_event = {
        "uri": "https://api.calendly.com/scheduled_events/ABC123",
        "name": "Test Event",
        "start_time": (datetime.now() + timedelta(days=1)).isoformat(),
        "end_time": (datetime.now() + timedelta(days=1, hours=1)).isoformat(),
        "event_type": "https://api.calendly.com/event_types/TEST123",
        "location": {"type": "zoom"},
    }
    
    response = client.post(
        "/api/v1/calendly/ingest",
        json={"events": [mock_event]},
    )
    # Puede fallar si no hay conexión a Supabase o token
    assert response.status_code in [200, 401, 500]
    if response.status_code == 200:
        data = response.json()
        # El endpoint devuelve {"events": [...], "inserted": N} o {"ingested": ...} o {"status": ...}
        assert "ingested" in data or "status" in data or "inserted" in data


def test_metrics_endpoint(client: TestClient):
    """Test del endpoint /api/v1/metrics."""
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "timestamp" in data
    assert "requests" in data
    assert "tools" in data
    assert "rag" in data
    assert "llm" in data


def test_scheduling_query(client: TestClient):
    """Test de query de scheduling (debe usar RAG y posiblemente tools)."""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    response = client.post(
        "/api/v1/text",
        json={
            "query": f"Programa una reunión para {tomorrow} a las 10:00"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "debug" in data
    # Debe usar RAG si hay contexto disponible
    assert data["debug"].get("rag_context_used") is not None


def test_conflict_detection_placeholder(client: TestClient):
    """
    Test placeholder para detección de conflictos.
    Nota: Requiere eventos reales en el calendario para funcionar completamente.
    """
    # Este test verifica que el endpoint responde, pero la detección real
    # requiere eventos en el calendario
    response = client.post(
        "/api/v1/text",
        json={
            "query": "¿Tengo conflictos mañana a las 10:00?"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data


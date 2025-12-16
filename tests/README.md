# Tests E2E y Smoke Tests

Este directorio contiene tests end-to-end (E2E) y smoke tests para el sistema de agentes.

## Estructura

- `test_e2e.py`: Tests E2E para funcionalidades principales
- `test_deduplication.py`: Tests para lógica de deduplicación de eventos
- `conftest.py`: Configuración compartida (fixtures)

## Ejecutar Tests

```bash
# Todos los tests
pytest tests/

# Solo tests E2E
pytest tests/test_e2e.py

# Con verbose
pytest tests/ -v

# Con coverage
pytest tests/ --cov=app --cov-report=html
```

## Tests Incluidos

### E2E Tests (`test_e2e.py`)

1. **test_text_endpoint_basic**: Test básico del endpoint `/api/v1/text`
2. **test_agenda_list**: Test de listado de agenda (atajo directo)
3. **test_confirmed_events**: Test de eventos confirmados
4. **test_email_send_endpoint**: Test de envío de email
5. **test_calendly_events_list**: Test de listado de eventos Calendly
6. **test_calendly_ingest**: Test de ingest de eventos Calendly
7. **test_metrics_endpoint**: Test del endpoint de métricas
8. **test_scheduling_query**: Test de query de scheduling con RAG
9. **test_conflict_detection_placeholder**: Placeholder para detección de conflictos

### Deduplication Tests (`test_deduplication.py`)

1. **test_dedup_logic**: Test de lógica de deduplicación
2. **test_extracted_events_source_field**: Test del campo 'source' en extracted_events

## Notas

- Algunos tests pueden fallar si no hay configuración completa (SMTP, OAuth, etc.)
- Los tests están diseñados para ser tolerantes a fallos de configuración
- Los tests de deduplicación requieren conexión a Supabase








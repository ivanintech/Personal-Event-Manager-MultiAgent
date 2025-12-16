"""
API endpoints para gestión de eventos sugeridos.

Endpoints para sugerir, listar, aprobar y rechazar eventos descubiertos.
Adaptado del proyecto final del curso para Event Manager.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..config.database import db
from ..agents.specialists.event_agent import EventAgent
from ..agents.specialists.calendar_agent import CalendarAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["Events"])


# Schemas
class SuggestEventRequest(BaseModel):
    """Request para sugerir un evento."""
    url: str = Field(..., description="URL del evento a procesar")
    source: str = Field(default="web", description="Fuente del evento (web, email, news, etc.)")


class SuggestEventResponse(BaseModel):
    """Response de sugerencia de evento."""
    success: bool
    event_id: Optional[int] = None
    event: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ApproveEventRequest(BaseModel):
    """Request para aprobar un evento."""
    notes: Optional[str] = Field(None, description="Notas opcionales al aprobar")


class RejectEventRequest(BaseModel):
    """Request para rechazar un evento."""
    reason: Optional[str] = Field(None, description="Razón del rechazo")


@router.post("/suggest", response_model=SuggestEventResponse)
async def suggest_event(request: SuggestEventRequest):
    """
    Sugiere un evento procesando una URL.
    
    Procesa la URL del evento, extrae información, genera resumen,
    determina relevancia y crea una entrada en extracted_events con status='suggested'.
    """
    try:
        # Inicializar EventAgent
        event_agent = EventAgent()
        
        # Procesar URL del evento
        result = await event_agent.suggest_event(
            url=request.url,
            source=request.source
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Error procesando evento")
            )
        
        suggested_event = result.get("suggested_event")
        
        # Preparar datos para insertar en extracted_events
        event_data = {
            "message_id": None,
            "title": suggested_event.get("title"),
            "start_at": suggested_event.get("start_at"),
            "end_at": suggested_event.get("end_at"),
            "timezone": "UTC",
            "location": suggested_event.get("location"),
            "attendees": None,
            "status": "suggested",  # Estado inicial
            "confidence": suggested_event.get("confidence", 0.5),
            "calendar_refs": None,
            "notes": suggested_event.get("description"),  # Usar descripción como notas
            "source": suggested_event.get("source", request.source)
        }
        
        # Insertar en base de datos
        inserted = await db.insert_extracted_events([event_data])
        
        if not inserted:
            raise HTTPException(
                status_code=500,
                detail="Error insertando evento en base de datos"
            )
        
        event_id = inserted[0].get("id")
        
        logger.info(f"Evento sugerido creado: ID={event_id}, URL={request.url}")
        
        return SuggestEventResponse(
            success=True,
            event_id=event_id,
            event=inserted[0],
            error=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sugiriendo evento: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando evento: {str(e)}"
        )


@router.get("/suggested")
async def list_suggested_events(
    limit: int = Query(default=50, ge=1, le=100, description="Número máximo de eventos"),
    offset: int = Query(default=0, ge=0, description="Offset para paginación")
):
    """
    Lista eventos sugeridos (status='suggested').
    
    Retorna eventos que están pendientes de aprobación.
    """
    try:
        events = await db.get_extracted_events(
            status="suggested",
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "events": events,
            "count": len(events),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error listando eventos sugeridos: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error listando eventos: {str(e)}"
        )


@router.get("")
async def list_all_events(
    status: Optional[str] = Query(None, description="Filtrar por status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Lista todos los eventos (o filtrados por status).
    """
    try:
        events = await db.get_extracted_events(
            status=status,
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "events": events,
            "count": len(events),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error listando eventos: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error listando eventos: {str(e)}"
        )


@router.post("/{event_id}/approve")
async def approve_event(
    event_id: int,
    request: ApproveEventRequest = ApproveEventRequest()
):
    """
    Aprueba un evento sugerido y lo crea en Google Calendar.
    
    Cambia el status a 'confirmed' y crea el evento en Google Calendar.
    """
    try:
        # Obtener evento de la base de datos
        events = await db.get_extracted_events(limit=1000)  # Obtener todos para buscar
        event = next((e for e in events if e.get("id") == event_id), None)
        
        if not event:
            raise HTTPException(
                status_code=404,
                detail=f"Evento {event_id} no encontrado"
            )
        
        if event.get("status") != "suggested":
            raise HTTPException(
                status_code=400,
                detail=f"Evento {event_id} no está en estado 'suggested' (actual: {event.get('status')})"
            )
        
        # Crear evento en Google Calendar
        calendar_agent = CalendarAgent()
        
        # Preparar datos para Calendar
        title = event.get("title", "Evento")
        start_at = event.get("start_at")
        end_at = event.get("end_at")
        
        if not start_at:
            raise HTTPException(
                status_code=400,
                detail="Evento no tiene fecha de inicio"
            )
        
        # Si no hay end_at, usar 1 hora por defecto
        if not end_at:
            from datetime import datetime, timedelta
            from dateutil import parser as date_parser
            start_dt = date_parser.parse(start_at)
            end_dt = start_dt + timedelta(hours=1)
            end_at = end_dt.isoformat()
        
        # Crear en Calendar
        calendar_result = await calendar_agent.create_event(
            summary=title,
            start_datetime=start_at,
            end_datetime=end_at,
            attendees=[],
            timezone=event.get("timezone", "UTC"),
            description=event.get("notes") or f"Evento sugerido desde {event.get('source', 'web')}"
        )
        
        if not calendar_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Error creando evento en Calendar: {calendar_result.get('error')}"
            )
        
        # Actualizar status en base de datos
        updates = {
            "status": "confirmed",
            "notes": request.notes or event.get("notes")
        }
        
        # Guardar referencia al evento de Calendar
        calendar_data = calendar_result.get("result", {})
        calendar_refs = {
            "provider": "google",
            "event_id": calendar_data.get("event_id"),
            "event_link": calendar_data.get("event_link")
        }
        
        updates["calendar_refs"] = calendar_refs
        
        updated_event = await db.update_extracted_event(event_id, updates)
        
        logger.info(f"Evento {event_id} aprobado y creado en Google Calendar")
        
        return {
            "success": True,
            "event_id": event_id,
            "calendar_event_id": calendar_data.get("event_id"),
            "calendar_link": calendar_data.get("event_link"),
            "event": updated_event
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error aprobando evento {event_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error aprobando evento: {str(e)}"
        )


@router.post("/{event_id}/reject")
async def reject_event(
    event_id: int,
    request: RejectEventRequest = RejectEventRequest()
):
    """
    Rechaza un evento sugerido.
    
    Cambia el status a 'rejected' y guarda la razón del rechazo.
    """
    try:
        # Obtener evento
        events = await db.get_extracted_events(limit=1000)
        event = next((e for e in events if e.get("id") == event_id), None)
        
        if not event:
            raise HTTPException(
                status_code=404,
                detail=f"Evento {event_id} no encontrado"
            )
        
        if event.get("status") != "suggested":
            raise HTTPException(
                status_code=400,
                detail=f"Evento {event_id} no está en estado 'suggested' (actual: {event.get('status')})"
            )
        
        # Actualizar status
        updates = {
            "status": "rejected",
            "notes": request.reason or "Rechazado por el usuario"
        }
        
        updated_event = await db.update_extracted_event(event_id, updates)
        
        logger.info(f"Evento {event_id} rechazado")
        
        return {
            "success": True,
            "event_id": event_id,
            "event": updated_event
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rechazando evento {event_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error rechazando evento: {str(e)}"
        )


@router.get("/{event_id}")
async def get_event(event_id: int):
    """
    Obtiene un evento específico por ID.
    """
    try:
        events = await db.get_extracted_events(limit=1000)
        event = next((e for e in events if e.get("id") == event_id), None)
        
        if not event:
            raise HTTPException(
                status_code=404,
                detail=f"Evento {event_id} no encontrado"
            )
        
        return {
            "success": True,
            "event": event
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo evento {event_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo evento: {str(e)}"
        )





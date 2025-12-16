"""
WhatsApp Batch Processing - Procesa conversaciones completas periódicamente.

Útil para detectar eventos que se mencionaron en múltiples mensajes
o que no se detectaron en tiempo real.
"""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, BackgroundTasks
import httpx

from ..config.settings import get_settings
from ..agents.graph import agent_orchestrator
from ..services.whatsapp_conversation import whatsapp_conversation_service
from ..agents.tools.calendar_tool import calendar_tool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/whatsapp", tags=["WhatsApp Batch"])
settings = get_settings()


@router.post("/process-conversations")
async def process_conversations_batch(background_tasks: BackgroundTasks):
    """
    Procesa conversaciones no procesadas en batch.
    
    Útil para:
    - Detectar eventos que se mencionaron en múltiples mensajes
    - Re-procesar conversaciones con mejor contexto
    - Detectar eventos que no se detectaron en tiempo real
    
    Returns:
        Número de conversaciones procesadas
    """
    try:
        # Obtener conversaciones no procesadas
        conversation_ids = await whatsapp_conversation_service.get_unprocessed_conversations(
            limit=50
        )
        
        if not conversation_ids:
            return {
                "status": "ok",
                "message": "No hay conversaciones sin procesar",
                "processed": 0,
            }
        
        # Procesar en background
        background_tasks.add_task(
            process_conversations_background,
            conversation_ids=conversation_ids,
        )
        
        return {
            "status": "processing",
            "message": f"Processing {len(conversation_ids)} conversations in background",
            "conversations": len(conversation_ids),
        }
        
    except Exception as e:
        logger.error(f"Error starting batch processing: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "processed": 0,
        }


async def process_conversations_background(conversation_ids: List[str]):
    """
    Procesa conversaciones en background.
    
    Para cada conversación:
    1. Obtiene todos los mensajes
    2. Construye contexto completo
    3. Procesa con agente para detectar eventos
    4. Crea eventos si se detectan
    """
    processed_count = 0
    events_created = 0
    
    for conversation_id in conversation_ids:
        try:
            logger.info(f"🔄 Processing conversation: {conversation_id}")
            
            # Obtener todos los mensajes de la conversación
            messages = await whatsapp_conversation_service.get_conversation_context(
                conversation_id=conversation_id,
                limit=50,  # Más mensajes para análisis completo
                include_processed=False,
            )
            
            if not messages:
                continue
            
            # Construir contexto completo
            chat_history = whatsapp_conversation_service.build_chat_history(
                messages=messages,
                include_system=True,
            )
            
            # Construir query para análisis completo
            # Combinar todos los mensajes en un solo contexto
            full_conversation = "\n\n".join([
                f"Usuario: {msg.get('body', '')}"
                for msg in messages
            ])
            
            query = (
                f"Analiza esta conversación completa de WhatsApp y detecta si hay eventos "
                f"mencionados (reuniones, citas, citas, etc.). Extrae toda la información "
                f"relevante: fechas, horas, títulos, participantes, ubicaciones.\n\n"
                f"Conversación:\n{full_conversation}"
            )
            
            # Procesar con agente
            result = await agent_orchestrator.run(
                query=query,
                chat_history=chat_history,
            )
            
            # Verificar si se creó evento
            tool_results = result.get("tool_results", [])
            event_created = False
            
            for tool_result in tool_results:
                if tool_result.get("tool_name") == "create_calendar_event":
                    if tool_result.get("success"):
                        event_created = True
                        events_created += 1
                        break
            
            # Si no se creó automáticamente, intentar extracción manual
            if not event_created:
                # Usar el procesador para extraer eventos del texto completo
                from ..services.whatsapp_processor import WhatsAppMessageProcessor
                processor = WhatsAppMessageProcessor()
                
                # Intentar extraer de cada mensaje
                for msg in messages:
                    extraction_result = await processor.extract_event_from_message(
                        message_body=msg.get("body", ""),
                        from_number=conversation_id,
                        message_sid=msg.get("message_sid", ""),
                    )
                    
                    if extraction_result.get("success") and extraction_result.get("event"):
                        event = extraction_result["event"]
                        create_result = await calendar_tool.execute(
                            summary=event.get("title", "Evento desde WhatsApp"),
                            start_datetime=event.get("start_at"),
                            end_datetime=event.get("end_at"),
                            description=f"Extraído de conversación WhatsApp:\n{full_conversation}",
                            timezone=event.get("timezone", "UTC"),
                        )
                        
                        if create_result.get("success"):
                            event_created = True
                            events_created += 1
                            # Marcar mensaje como procesado
                            await whatsapp_conversation_service.mark_message_processed(
                                message_sid=msg.get("message_sid"),
                                event_extracted=True,
                                event_id=create_result.get("result", {}).get("event_id"),
                            )
                            break
            
            # Marcar todos los mensajes como procesados
            for msg in messages:
                await whatsapp_conversation_service.mark_message_processed(
                    message_sid=msg.get("message_sid"),
                    event_extracted=event_created,
                )
            
            processed_count += 1
            
        except Exception as e:
            logger.error(
                f"Error processing conversation {conversation_id}: {e}",
                exc_info=True
            )
            continue
    
    logger.info(
        f"✅ Batch processing complete: {processed_count} conversations, "
        f"{events_created} events created"
    )


@router.get("/conversations")
async def list_conversations(limit: int = 20):
    """
    Lista conversaciones de WhatsApp.
    
    Returns:
        Lista de conversaciones con estadísticas
    """
    try:
        # Obtener conversaciones desde Supabase
        base_url = f"{settings.supabase_url.rstrip('/')}/rest/v1"
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            # Obtener conversaciones únicas
            response = await client.get(
                f"{base_url}/whatsapp_conversations",
                headers=headers,
                params={
                    "order": "last_message_at.desc",
                    "limit": str(limit),
                },
            )
            response.raise_for_status()
            conversations = response.json()
            
            return {
                "status": "ok",
                "conversations": conversations,
                "count": len(conversations),
            }
            
    except Exception as e:
        logger.error(f"Error listing conversations: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "conversations": [],
        }


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str, limit: int = 50):
    """
    Obtiene mensajes de una conversación específica.
    
    Args:
        conversation_id: ID de la conversación (from_number)
        limit: Número máximo de mensajes
        
    Returns:
        Lista de mensajes de la conversación
    """
    try:
        messages = await whatsapp_conversation_service.get_conversation_context(
            conversation_id=conversation_id,
            limit=limit,
            include_processed=True,  # Incluir todos los mensajes
        )
        
        return {
            "status": "ok",
            "conversation_id": conversation_id,
            "messages": messages,
            "count": len(messages),
        }
        
    except Exception as e:
        logger.error(f"Error getting conversation messages: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "messages": [],
        }



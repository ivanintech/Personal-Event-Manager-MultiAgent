"""
WhatsApp Webhook Handler - Recibe y procesa mensajes de Twilio WhatsApp.

Flujo:
1. Twilio envía webhook cuando llega un mensaje
2. Validamos la firma de Twilio
3. Procesamos el mensaje para detectar intención de crear evento
4. Extraemos información del evento (fecha, hora, título)
5. Creamos el evento automáticamente
6. Respondemos por WhatsApp confirmando
"""

import logging
import hmac
import hashlib
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from ..config.settings import get_settings
from ..agents.graph import agent_orchestrator
from ..agents.tools.whatsapp_tool import whatsapp_tool
from ..services.whatsapp_processor import WhatsAppMessageProcessor
from ..services.whatsapp_conversation import whatsapp_conversation_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/whatsapp", tags=["WhatsApp"])
settings = get_settings()

# Procesador de mensajes WhatsApp
message_processor = WhatsAppMessageProcessor()

# Intentar importar RequestValidator de Twilio (opcional)
try:
    from twilio.request_validator import RequestValidator
    TWILIO_VALIDATOR_AVAILABLE = True
except ImportError:
    TWILIO_VALIDATOR_AVAILABLE = False
    logger.warning("twilio package not installed, signature validation will be skipped")


def _validate_twilio_signature(request: Request, body: bytes) -> bool:
    """
    Valida la firma de Twilio usando RequestValidator.
    
    Twilio envía un header X-Twilio-Signature que debemos validar
    contra la URL completa y el body del request.
    """
    if not TWILIO_VALIDATOR_AVAILABLE:
        logger.warning("Twilio RequestValidator not available, skipping signature validation")
        return True  # Permitir en desarrollo si no está instalado
    
    try:
        validator = RequestValidator(settings.twilio_auth_token)
        
        # Obtener la URL completa
        url = str(request.url)
        
        # Obtener la firma del header
        signature = request.headers.get("X-Twilio-Signature", "")
        
        # Validar
        is_valid = validator.validate(url, body, signature)
        
        if not is_valid:
            logger.warning(f"Twilio signature validation failed for URL: {url}")
        
        return is_valid
    except Exception as e:
        logger.error(f"Error validating Twilio signature: {e}", exc_info=True)
        return False


@router.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook receptor de mensajes de Twilio WhatsApp.
    
    Twilio envía un POST cuando llega un mensaje a tu número de WhatsApp.
    
    Formato del payload de Twilio:
    {
        "MessageSid": "...",
        "AccountSid": "...",
        "From": "whatsapp:+1234567890",
        "To": "whatsapp:+0987654321",
        "Body": "Mensaje del usuario",
        "NumMedia": "0"
    }
    
    Validación:
    - Valida la firma X-Twilio-Signature para asegurar que viene de Twilio
    - Si TWILIO_AUTH_TOKEN no está configurado, salta validación (solo para desarrollo)
    
    Procesamiento:
    - Procesa el mensaje en background para no bloquear la respuesta a Twilio
    - Detecta si el mensaje requiere crear un evento
    - Extrae información del evento
    - Crea el evento automáticamente
    - Responde por WhatsApp
    """
    try:
        # Leer body como bytes para validación
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")
        
        # Validar firma de Twilio (si está configurado)
        if settings.twilio_auth_token:
            if not _validate_twilio_signature(request, body_bytes):
                logger.warning("Twilio signature validation failed")
                raise HTTPException(status_code=403, detail="Invalid Twilio signature")
        else:
            logger.warning("TWILIO_AUTH_TOKEN not configured, skipping signature validation (DEVELOPMENT ONLY)")
        
        # Parsear form data de Twilio
        form_data = await request.form()
        
        # Extraer información del mensaje
        message_sid = form_data.get("MessageSid", "")
        from_number = form_data.get("From", "").replace("whatsapp:", "")
        to_number = form_data.get("To", "").replace("whatsapp:", "")
        message_body = form_data.get("Body", "")
        num_media = int(form_data.get("NumMedia", "0"))
        
        logger.info(
            f"📨 WhatsApp message received: From={from_number}, "
            f"Body='{message_body[:50]}...', SID={message_sid}"
        )
        
        # Almacenar mensaje en Supabase (síncrono para evitar pérdidas)
        try:
            await whatsapp_conversation_service.store_message(
                message_sid=message_sid,
                from_number=from_number,
                to_number=to_number,
                body=message_body,
                num_media=num_media,
            )
        except Exception as e:
            logger.error(f"Error storing WhatsApp message: {e}", exc_info=True)
            # Continuar aunque falle el almacenamiento
        
        # Procesar mensaje en background (no bloquear respuesta a Twilio)
        background_tasks.add_task(
            process_whatsapp_message,
            message_sid=message_sid,
            from_number=from_number,
            to_number=to_number,
            message_body=message_body,
            num_media=num_media,
        )
        
        # Responder inmediatamente a Twilio (Twilio espera respuesta rápida)
        # Enviaremos la respuesta real en el background task
        return {"status": "received", "message": "Processing message"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {e}", exc_info=True)
        # Aún así respondemos 200 para que Twilio no reintente
        return {"status": "error", "message": str(e)}


async def process_whatsapp_message(
    message_sid: str,
    from_number: str,
    to_number: str,
    message_body: str,
    num_media: int,
):
    """
    Procesa un mensaje de WhatsApp en background.
    
    Flujo:
    1. Detecta si el mensaje requiere crear un evento
    2. Extrae información del evento (fecha, hora, título)
    3. Crea el evento en Google Calendar
    4. Responde por WhatsApp confirmando
    """
    try:
        logger.info(f"🔄 Processing WhatsApp message: {message_sid}")
        
        # 1. Obtener contexto de la conversación (últimos 10 mensajes)
        conversation_id = from_number
        conversation_context = await whatsapp_conversation_service.get_conversation_context(
            conversation_id=conversation_id,
            limit=10,
            include_processed=False,  # Solo mensajes no procesados
        )
        
        # 2. Construir historial de chat para el agente
        chat_history = whatsapp_conversation_service.build_chat_history(
            messages=conversation_context,
            include_system=True,
        )
        
        # 3. Detectar intención usando el agente CON CONTEXTO
        # El agente ahora tiene acceso a toda la conversación
        result = await agent_orchestrator.run(
            query=message_body,
            chat_history=chat_history,  # ← Contexto completo de la conversación
        )
        
        # 2. Verificar si se detectó intención de calendar/scheduling
        intent_detected = False
        tool_calls = result.get("tool_calls", [])
        tool_results = result.get("tool_results", [])
        
        # Buscar si se llamó a create_calendar_event
        event_created = False
        event_details = None
        
        for tool_result in tool_results:
            if tool_result.get("tool_name") == "create_calendar_event":
                if tool_result.get("success"):
                    event_created = True
                    event_details = tool_result.get("result", {})
                    break
        
        # 3. Si no se creó automáticamente, intentar extraer y crear manualmente
        if not event_created:
            # Usar el procesador de mensajes para extraer eventos
            extraction_result = await message_processor.extract_event_from_message(
                message_body=message_body,
                from_number=from_number,
                message_sid=message_sid,
            )
            
            if extraction_result.get("success") and extraction_result.get("event"):
                # Crear evento usando calendar_tool
                from ..agents.tools.calendar_tool import calendar_tool
                
                event = extraction_result["event"]
                create_result = await calendar_tool.execute(
                    summary=event.get("title", "Evento desde WhatsApp"),
                    start_datetime=event.get("start_at"),
                    end_datetime=event.get("end_at"),
                    description=f"Mensaje: {message_body}",
                    timezone=event.get("timezone", "UTC"),
                )
                
                if create_result.get("success"):
                    event_created = True
                    event_details = create_result.get("result", {})
        
        # 4. Responder por WhatsApp
        if event_created and event_details:
            response_text = (
                f"✅ Evento creado exitosamente!\n\n"
                f"📅 {event_details.get('summary', 'Evento')}\n"
                f"🕐 {event_details.get('start', {}).get('dateTime', 'N/A')}\n"
            )
            if event_details.get("meet_link"):
                response_text += f"🔗 Meet: {event_details['meet_link']}\n"
            if event_details.get("event_link"):
                response_text += f"📎 Calendario: {event_details['event_link']}\n"
        else:
            # Si no se pudo crear evento, responder con la respuesta del agente
            agent_response = result.get("text", "Recibido. ¿En qué puedo ayudarte?")
            response_text = agent_response[:500]  # Limitar longitud
        
        # Enviar respuesta por WhatsApp
        send_result = await whatsapp_tool.execute(
            to=from_number,
            message=response_text,
        )
        
        if send_result.get("success"):
            logger.info(f"✅ WhatsApp response sent to {from_number}")
        else:
            logger.error(f"❌ Failed to send WhatsApp response: {send_result.get('error')}")
        
        # 6. Marcar mensaje como procesado
        await whatsapp_conversation_service.mark_message_processed(
            message_sid=message_sid,
            event_extracted=event_created,
            event_id=event_details.get("event_id") if event_details else None,
        )
        
    except Exception as e:
        logger.error(f"❌ Error processing WhatsApp message: {e}", exc_info=True)
        # Intentar enviar mensaje de error
        try:
            await whatsapp_tool.execute(
                to=from_number,
                message="❌ Lo siento, hubo un error procesando tu mensaje. Por favor intenta de nuevo.",
            )
        except Exception:
            pass


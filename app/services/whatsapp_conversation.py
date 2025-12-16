"""
WhatsApp Conversation Service - Gestiona conversaciones completas de WhatsApp.

Almacena mensajes y procesa conversaciones con contexto completo para detectar eventos.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx

from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class WhatsAppConversationService:
    """
    Servicio para gestionar conversaciones de WhatsApp.
    
    Funcionalidades:
    - Almacenar mensajes en Supabase
    - Obtener contexto de conversaciones
    - Procesar conversaciones completas para detectar eventos
    """
    
    def __init__(self):
        self.supabase_url = settings.supabase_url.rstrip("/")
        self.supabase_key = settings.supabase_service_role_key
        self.base_url = f"{self.supabase_url}/rest/v1"
        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
        }
    
    async def store_message(
        self,
        message_sid: str,
        from_number: str,
        to_number: str,
        body: str,
        num_media: int = 0,
        media_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Almacena un mensaje de WhatsApp en Supabase.
        
        Args:
            message_sid: SID único de Twilio
            from_number: Número del remitente
            to_number: Número de destino
            body: Contenido del mensaje
            num_media: Número de archivos adjuntos
            media_urls: URLs de archivos adjuntos
            
        Returns:
            Mensaje almacenado con ID
        """
        conversation_id = from_number  # Usar número como ID de conversación
        
        message_data = {
            "message_sid": message_sid,
            "conversation_id": conversation_id,
            "from_number": from_number,
            "to_number": to_number,
            "body": body,
            "received_at": datetime.utcnow().isoformat() + "Z",
            "num_media": num_media,
            "processed": False,
            "event_extracted": False,
        }
        
        if media_urls:
            message_data["media_urls"] = media_urls
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/whatsapp_messages",
                    headers=self.headers,
                    json=message_data,
                )
                response.raise_for_status()
                stored_message = response.json()
                
                logger.info(
                    f"✅ WhatsApp message stored: SID={message_sid}, "
                    f"conversation={conversation_id}"
                )
                
                return stored_message[0] if isinstance(stored_message, list) else stored_message
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:  # Duplicado
                logger.debug(f"Message {message_sid} already exists, skipping")
                # Obtener el mensaje existente
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(
                        f"{self.base_url}/whatsapp_messages",
                        headers=self.headers,
                        params={"message_sid": f"eq.{message_sid}"},
                    )
                    if response.status_code == 200:
                        messages = response.json()
                        if messages:
                            return messages[0]
            raise
        except Exception as e:
            logger.error(f"Error storing WhatsApp message: {e}", exc_info=True)
            raise
    
    async def get_conversation_context(
        self,
        conversation_id: str,
        limit: int = 10,
        include_processed: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Obtiene el contexto de una conversación (últimos N mensajes).
        
        Args:
            conversation_id: ID de la conversación (from_number)
            limit: Número de mensajes a obtener
            include_processed: Incluir mensajes ya procesados
            
        Returns:
            Lista de mensajes ordenados por fecha (más antiguo primero)
        """
        params = {
            "conversation_id": f"eq.{conversation_id}",
            "order": "received_at.asc",
            "limit": str(limit),
        }
        
        if not include_processed:
            params["processed"] = "eq.false"
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}/whatsapp_messages",
                    headers=self.headers,
                    params=params,
                )
                response.raise_for_status()
                messages = response.json()
                
                logger.info(
                    f"📚 Retrieved {len(messages)} messages for conversation {conversation_id}"
                )
                
                return messages
                
        except Exception as e:
            logger.error(f"Error getting conversation context: {e}", exc_info=True)
            return []
    
    def build_chat_history(
        self,
        messages: List[Dict[str, Any]],
        include_system: bool = True,
    ) -> List[Dict[str, str]]:
        """
        Construye historial de chat para el agente desde mensajes almacenados.
        
        Args:
            messages: Lista de mensajes de la conversación
            include_system: Incluir mensaje del sistema inicial
            
        Returns:
            Lista de mensajes en formato para el agente
        """
        history = []
        
        if include_system:
            history.append({
                "role": "system",
                "content": (
                    "Eres un asistente que ayuda a detectar y crear eventos desde conversaciones de WhatsApp. "
                    "Analiza los mensajes y detecta si hay intención de crear eventos (reuniones, citas, etc.). "
                    "Extrae información como fecha, hora, título y participantes."
                ),
            })
        
        for msg in messages:
            # Mensajes del usuario (from_number)
            history.append({
                "role": "user",
                "content": msg.get("body", ""),
            })
            
            # Si hay respuesta del bot almacenada, incluirla
            # (Por ahora solo tenemos mensajes entrantes)
        
        return history
    
    async def mark_message_processed(
        self,
        message_sid: str,
        event_extracted: bool = False,
        event_id: Optional[int] = None,
    ) -> bool:
        """
        Marca un mensaje como procesado.
        
        Args:
            message_sid: SID del mensaje
            event_extracted: Si se extrajo un evento
            event_id: ID del evento extraído (opcional)
            
        Returns:
            True si se actualizó correctamente
        """
        update_data = {
            "processed": True,
            "event_extracted": event_extracted,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        
        if event_id:
            update_data["event_id"] = event_id
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.patch(
                    f"{self.base_url}/whatsapp_messages",
                    headers={**self.headers, "Prefer": "return=representation"},
                    params={"message_sid": f"eq.{message_sid}"},
                    json=update_data,
                )
                response.raise_for_status()
                
                logger.debug(f"✅ Message {message_sid} marked as processed")
                return True
                
        except Exception as e:
            logger.error(f"Error marking message as processed: {e}", exc_info=True)
            return False
    
    async def get_unprocessed_conversations(
        self,
        limit: int = 10,
    ) -> List[str]:
        """
        Obtiene lista de conversaciones con mensajes no procesados.
        
        Args:
            limit: Número máximo de conversaciones
            
        Returns:
            Lista de conversation_id
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Obtener conversaciones únicas con mensajes no procesados
                response = await client.get(
                    f"{self.base_url}/whatsapp_messages",
                    headers=self.headers,
                    params={
                        "processed": "eq.false",
                        "select": "conversation_id",
                        "order": "received_at.desc",
                    },
                )
                response.raise_for_status()
                messages = response.json()
                
                # Extraer conversation_ids únicos
                conversation_ids = list(set(
                    msg.get("conversation_id") 
                    for msg in messages 
                    if msg.get("conversation_id")
                ))[:limit]
                
                return conversation_ids
                
        except Exception as e:
            logger.error(f"Error getting unprocessed conversations: {e}", exc_info=True)
            return []


# Instancia global
whatsapp_conversation_service = WhatsAppConversationService()



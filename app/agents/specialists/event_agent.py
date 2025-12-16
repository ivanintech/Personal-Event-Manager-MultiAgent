"""
EventAgent: Especializado en descubrimiento y procesamiento de eventos.

Procesa URLs de eventos, extrae información, genera resúmenes y determina relevancia.
Adaptado del proyecto final del curso para Event Manager.
"""

import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dateutil import parser as date_parser

from ...config.settings import get_settings
from ...agents.tool_exec import execute_tool
from ...services.rag import rag_service
from ...services.chat import chat_service

logger = logging.getLogger(__name__)


class EventAgent:
    """
    Agente especializado en descubrimiento y procesamiento de eventos.
    
    Funcionalidades:
    - Procesa URLs de eventos usando web scraping
    - Extrae información estructurada (fecha, hora, lugar)
    - Genera resúmenes con LLM
    - Determina relevancia usando RAG
    """

    def __init__(self, rag_service=None, chat_service=None):
        """
        Inicializa EventAgent.
        
        Args:
            rag_service: Optional RAG service (para dependency injection)
            chat_service: Optional chat service (para dependency injection)
        """
        self.settings = get_settings()
        self.name = "EventAgent"
        
        # Use injected services or fallback to global singletons
        from ...services.rag import rag_service as default_rag_service
        from ...services.chat import chat_service as default_chat_service
        self.rag_service = rag_service if rag_service is not None else default_rag_service
        self.chat_service = chat_service if chat_service is not None else default_chat_service

    def _extract_date_from_text(self, text: str) -> Optional[str]:
        """
        Intenta extraer una fecha del texto usando dateutil.
        
        Args:
            text: Texto que puede contener una fecha
            
        Returns:
            Fecha en formato ISO o None
        """
        if not text:
            return None
        
        # Buscar patrones comunes de fecha
        date_patterns = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # DD/MM/YYYY
            r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',    # YYYY/MM/DD
            r'\d{1,2}\s+\w+\s+\d{4}',           # DD Month YYYY
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            if matches:
                try:
                    parsed_date = date_parser.parse(matches[0], fuzzy=True)
                    return parsed_date.isoformat()
                except (ValueError, date_parser.ParserError):
                    continue
        
        # Intentar parsear todo el texto
        try:
            parsed_date = date_parser.parse(text, fuzzy=True)
            return parsed_date.isoformat()
        except (ValueError, date_parser.ParserError):
            return None

    def _extract_time_from_text(self, text: str) -> Optional[str]:
        """
        Intenta extraer una hora del texto.
        
        Args:
            text: Texto que puede contener una hora
            
        Returns:
            Hora en formato HH:MM o None
        """
        if not text:
            return None
        
        # Patrones comunes de hora
        time_patterns = [
            r'\b(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)\b',  # 3:30 PM
            r'\b(\d{1,2}):(\d{2})\b',                   # 15:30
            r'\b(\d{1,2})\s*(AM|PM|am|pm)\b',          # 3 PM
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0][0] + ':' + matches[0][1] if len(matches[0]) > 1 else None
        
        return None

    def _extract_location_from_text(self, text: str) -> Optional[str]:
        """
        Intenta extraer una ubicación del texto.
        
        Args:
            text: Texto que puede contener una ubicación
            
        Returns:
            Ubicación extraída o None
        """
        if not text:
            return None
        
        # Buscar palabras clave de ubicación
        location_keywords = ['en', 'at', 'ubicado', 'lugar', 'location', 'venue', 'dirección']
        
        for keyword in location_keywords:
            pattern = rf'{keyword}[: ]\s*([^.,\n]+)'
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return matches[0].strip()
        
        return None

    async def _determine_relevance(
        self,
        event_title: str,
        event_description: Optional[str] = None
    ) -> float:
        """
        Determina la relevancia de un evento usando RAG.
        
        Compara el evento con el contexto histórico del usuario (preferencias,
        eventos anteriores, intereses) almacenados en RAG.
        
        Args:
            event_title: Título del evento
            event_description: Descripción opcional del evento
            
        Returns:
            Score de relevancia entre 0.0 y 1.0
        """
        try:
            # Construir query para RAG
            query = f"¿Es relevante este evento para el usuario? {event_title}"
            if event_description:
                query += f" {event_description}"
            
            # Buscar contexto relevante en RAG
            rag_result = await self.rag_service.answer_query(query, top_k=3)
            
            # Si hay contexto relevante, el evento es más relevante
            context_blocks = rag_result.get('debug', {}).get('top_doc_ids', [])
            
            if context_blocks:
                # Si hay contexto, calcular relevancia basada en similitud
                # Por ahora, retornamos un score basado en si hay contexto
                return 0.7  # Relevancia media-alta si hay contexto
            else:
                # Sin contexto, relevancia baja
                return 0.3
            
        except Exception as e:
            logger.error(f"Error determinando relevancia: {e}")
            # En caso de error, retornar relevancia media
            return 0.5

    async def _generate_event_summary(
        self,
        title: str,
        description: Optional[str] = None,
        scraped_content: Optional[str] = None
    ) -> str:
        """
        Genera un resumen conciso del evento usando LLM.
        
        Args:
            title: Título del evento
            description: Descripción del evento (si existe)
            scraped_content: Contenido scrapeado de la página
            
        Returns:
            Resumen de 2-3 líneas del evento
        """
        try:
            # Construir prompt para generar resumen
            content = description or scraped_content or title
            
            prompt = f"""Genera un resumen conciso de 2-3 líneas sobre este evento:

Título: {title}
Contenido: {content[:500]}

Resumen (2-3 líneas, en español):"""

            # Usar chat service para generar resumen
            summary = await self.chat_service.generate_answer(
                prompt,
                context_blocks=[]  # No necesitamos contexto adicional
            )
            
            # Limitar a 3 líneas máximo
            lines = summary.split('\n')[:3]
            summary = '\n'.join(lines).strip()
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generando resumen: {e}")
            # Fallback: usar descripción o título
            return description or title

    async def process_event_url(
        self,
        url: str,
        source: str = "web"
    ) -> Dict[str, Any]:
        """
        Procesa una URL de evento y extrae información estructurada.
        
        Args:
            url: URL de la página del evento
            source: Fuente del evento (web, email, news, etc.)
            
        Returns:
            Dict con información del evento procesado:
            {
                "success": bool,
                "event": {
                    "title": str,
                    "description": str,
                    "summary": str,
                    "start_at": Optional[str],  # ISO format
                    "end_at": Optional[str],     # ISO format
                    "location": Optional[str],
                    "source_url": str,
                    "image_url": Optional[str],
                    "relevance_score": float,
                    "source": str
                },
                "error": Optional[str]
            }
        """
        try:
            # 1. Scrapear contenido de la URL
            logger.info(f"Scrapeando URL de evento: {url}")
            scrape_result = await execute_tool(
                "scrape_web_content",
                url=url,
                extract_image=True,
                extract_text=True
            )
            
            if not scrape_result.get("success"):
                return {
                    "success": False,
                    "error": f"Error scrapeando URL: {scrape_result.get('error', 'Unknown error')}",
                    "event": None
                }
            
            # 2. Extraer información básica
            title = scrape_result.get("title", "Evento sin título")
            description = scrape_result.get("description")
            image_url = scrape_result.get("image_url")
            text_content = scrape_result.get("text_content", "")
            
            # 3. Intentar extraer fecha, hora y lugar del contenido
            full_text = f"{title} {description or ''} {text_content}"
            
            # Extraer fecha
            extracted_date = self._extract_date_from_text(full_text)
            
            # Extraer hora
            extracted_time = self._extract_time_from_text(full_text)
            
            # Construir start_at si tenemos fecha
            start_at = None
            if extracted_date:
                if extracted_time:
                    start_at = f"{extracted_date.split('T')[0]}T{extracted_time}:00"
                else:
                    start_at = extracted_date
            
            # Extraer ubicación
            location = self._extract_location_from_text(full_text)
            
            # 4. Generar resumen con LLM
            logger.info(f"Generando resumen para evento: {title}")
            summary = await self._generate_event_summary(
                title=title,
                description=description,
                scraped_content=text_content[:500]  # Limitar contenido
            )
            
            # 5. Determinar relevancia usando RAG
            logger.info(f"Determinando relevancia para evento: {title}")
            relevance_score = await self._determine_relevance(
                event_title=title,
                event_description=description
            )
            
            # 6. Construir estructura de evento
            event_data = {
                "title": title,
                "description": description or summary,
                "summary": summary,
                "start_at": start_at,
                "end_at": None,  # Por ahora no extraemos end_at
                "location": location,
                "source_url": url,
                "image_url": image_url,
                "relevance_score": relevance_score,
                "source": source
            }
            
            logger.info(f"Evento procesado exitosamente: {title} (relevancia: {relevance_score:.2f})")
            
            return {
                "success": True,
                "event": event_data,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error procesando URL de evento {url}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "event": None
            }

    async def suggest_event(
        self,
        url: str,
        source: str = "web"
    ) -> Dict[str, Any]:
        """
        Sugiere un evento al usuario (procesa y crea entrada sugerida).
        
        Este método procesa la URL y retorna la estructura lista para
        guardar en extracted_events con status='suggested'.
        
        Args:
            url: URL del evento
            source: Fuente del evento
            
        Returns:
            Dict con evento sugerido listo para guardar
        """
        result = await self.process_event_url(url, source)
        
        if not result.get("success"):
            return result
        
        event = result.get("event")
        
        # Retornar estructura compatible con extracted_events
        return {
            "success": True,
            "suggested_event": {
                "title": event.get("title"),
                "description": event.get("summary"),  # Usar resumen como descripción
                "start_at": event.get("start_at"),
                "end_at": event.get("end_at"),
                "location": event.get("location"),
                "source_url": event.get("source_url"),
                "image_url": event.get("image_url"),
                "relevance_score": event.get("relevance_score"),
                "source": event.get("source"),
                "status": "suggested",  # Estado inicial
                "confidence": event.get("relevance_score", 0.5)  # Usar relevancia como confianza
            },
            "error": None
        }





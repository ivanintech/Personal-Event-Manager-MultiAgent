"""
WhatsApp Message Processor - Procesa mensajes de WhatsApp y extrae eventos.

Usa la misma lógica que extract_events_from_messages.py pero adaptada
para procesar mensajes de WhatsApp en tiempo real.
"""

import logging
import re
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Timezone por defecto
DEFAULT_TZ = timezone.utc

# Patrones de fecha/hora (simplificados del script original)
DATE_TIME_PATTERNS = [
    # 14/12/2025 16:00, 14-12-25 16:00
    r"(?P<d>\d{1,2})[/-](?P<m>\d{1,2})[/-](?P<y>\d{2,4})[ T](?P<h>\d{1,2}):(?P<min>\d{2})(?:[ ]?(?P<tz>(?:UTC|CET|CEST|GMT|[+-]\d{2}:?\d{2})))?",
    # 2025-12-14 16:00
    r"(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})[ T](?P<h>\d{2}):(?P<min>\d{2})(?:[ ]?(?P<tz>(?:UTC|CET|CEST|GMT|[+-]\d{2}:?\d{2})))?",
]

TIME_ONLY = r"(?P<h>\d{1,2}):(?P<min>\d{2})(?:[ ]?(?P<tz>(?:UTC|CET|CEST|GMT|[+-]\d{2}:?\d{2})))?"
TIME_RANGE = r"(?P<h1>\d{1,2}):(?P<m1>\d{2})\s*[-–]\s*(?P<h2>\d{1,2}):(?P<m2>\d{2})(?:[ ]?(?P<tz>(?:UTC|CET|CEST|GMT|[+-]\d{2}:?\d{2})))?"

WEEKDAYS = {
    # español
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, 
    "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
    # inglés
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, 
    "friday": 4, "saturday": 5, "sunday": 6,
}

RELATIVE = {
    "hoy": 0, "today": 0,
    "mañana": 1, "manana": 1, "tomorrow": 1,
    "pasado mañana": 2, "pasado manana": 2, "day after tomorrow": 2,
}

# Keywords que indican intención de crear evento
EVENT_KEYWORDS = [
    "reunión", "reunion", "meeting", "cita", "appointment",
    "agenda", "agendar", "programar", "schedule",
    "evento", "event", "conferencia", "conference",
    "llamada", "call", "videollamada", "videocall",
    "presentación", "presentacion", "presentation",
]


def apply_tz(dt: datetime, tz_str: Optional[str], default_tz: timezone) -> datetime:
    """Aplica timezone a datetime."""
    if not tz_str:
        return dt.replace(tzinfo=default_tz)
    # Simplificado: solo maneja UTC, CET, CEST
    tz_map = {
        "UTC": timezone.utc,
        "CET": timezone(timedelta(hours=1)),
        "CEST": timezone(timedelta(hours=2)),
        "GMT": timezone.utc,
    }
    tz = tz_map.get(tz_str.upper(), default_tz)
    return dt.replace(tzinfo=tz)


def next_weekday(from_dt: datetime, target_wd: int) -> datetime:
    """Encuentra el siguiente día de la semana."""
    days_ahead = target_wd - from_dt.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return from_dt + timedelta(days=days_ahead)


def parse_datetime_from_text(
    text: str, 
    received_at: Optional[datetime] = None,
    default_tz: timezone = DEFAULT_TZ
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Extrae fecha/hora de un texto.
    
    Returns:
        (start_datetime, end_datetime) o (None, None) si no se encuentra
    """
    text = text or ""
    text_lower = text.lower()
    received_at = received_at or datetime.now(default_tz)

    # Rango explícito hh:mm-hh:mm
    m_range = re.search(TIME_RANGE, text)
    if m_range:
        gd = m_range.groupdict()
        base = received_at
        tz_tok = gd.get("tz")
        start = base.replace(hour=int(gd["h1"]), minute=int(gd["m1"]), second=0, microsecond=0)
        end = base.replace(hour=int(gd["h2"]), minute=int(gd["m2"]), second=0, microsecond=0)
        start = apply_tz(start, tz_tok, default_tz)
        end = apply_tz(end, tz_tok, default_tz)
        
        # weekday relativo
        for wd_name, wd_idx in WEEKDAYS.items():
            if wd_name in text_lower:
                start = next_weekday(start, wd_idx)
                end = next_weekday(end, wd_idx)
                break
        
        # relativo hoy/mañana
        for rel, offset in RELATIVE.items():
            if rel in text_lower:
                start = start + timedelta(days=offset)
                end = end + timedelta(days=offset)
                break
        return start, end

    # Fecha completa
    for pat in DATE_TIME_PATTERNS:
        m = re.search(pat, text)
        if m:
            gd = m.groupdict()
            y = int(gd["y"])
            if y < 100:
                y += 2000
            start = datetime(
                y, int(gd["m"]), int(gd["d"]),
                int(gd["h"]), int(gd["min"]),
                tzinfo=default_tz,
            )
            start = apply_tz(start, gd.get("tz"), default_tz)
            
            # relativo
            for rel, offset in RELATIVE.items():
                if rel in text_lower:
                    start = start + timedelta(days=offset)
                    break
            
            # Duración por defecto: 1 hora
            end = start + timedelta(hours=1)
            return start, end
    
    # Solo hora
    m = re.search(TIME_ONLY, text)
    if m:
        base = received_at
        tz_tok = m.groupdict().get("tz")
        start = base.replace(
            hour=int(m.group("h")), 
            minute=int(m.group("min")), 
            second=0, 
            microsecond=0
        )
        start = apply_tz(start, tz_tok, default_tz)
        
        # weekday
        for wd_name, wd_idx in WEEKDAYS.items():
            if wd_name in text_lower:
                start = next_weekday(start, wd_idx)
                break
        
        # relativo
        for rel, offset in RELATIVE.items():
            if rel in text_lower:
                start = start + timedelta(days=offset)
                break
        
        end = start + timedelta(hours=1)
        return start, end
    
    return None, None


def detect_event_intent(text: str) -> bool:
    """
    Detecta si un mensaje tiene intención de crear un evento.
    
    Busca keywords relacionados con eventos y fechas/horas.
    """
    text_lower = text.lower()
    
    # Buscar keywords de eventos
    has_event_keyword = any(keyword in text_lower for keyword in EVENT_KEYWORDS)
    
    # Buscar indicadores de fecha/hora
    has_datetime = bool(parse_datetime_from_text(text)[0])
    
    # Si tiene keyword de evento Y fecha/hora, es muy probable que quiera crear evento
    if has_event_keyword and has_datetime:
        return True
    
    # Si tiene fecha/hora explícita, también puede ser intención
    if has_datetime:
        return True
    
    return False


def extract_title_from_message(text: str) -> str:
    """
    Extrae un título del mensaje.
    
    Estrategias:
    1. Primera línea si tiene más de 5 caracteres
    2. Texto antes de la fecha/hora
    3. Keyword + contexto
    """
    lines = text.strip().split("\n")
    if lines and len(lines[0]) > 5:
        # Limpiar la primera línea
        title = lines[0].strip()
        # Remover emojis comunes
        title = re.sub(r"[📅🕐📌✅❌]", "", title).strip()
        if title:
            return title[:100]  # Limitar longitud
    
    # Si no hay primera línea buena, buscar antes de fecha/hora
    # Simplificado: devolver primeras palabras
    words = text.split()[:5]
    if words:
        return " ".join(words)[:100]
    
    return "Evento desde WhatsApp"


class WhatsAppMessageProcessor:
    """
    Procesador de mensajes de WhatsApp.
    
    Extrae eventos de mensajes y los prepara para crear en Google Calendar.
    """
    
    async def extract_event_from_message(
        self,
        message_body: str,
        from_number: str,
        message_sid: str,
    ) -> Dict[str, Any]:
        """
        Extrae información de evento de un mensaje de WhatsApp.
        
        Args:
            message_body: Texto del mensaje
            from_number: Número de teléfono del remitente
            message_sid: SID del mensaje de Twilio
            
        Returns:
            {
                "success": bool,
                "event": {
                    "title": str,
                    "start_at": str (ISO format),
                    "end_at": str (ISO format),
                    "timezone": str,
                    "description": str,
                } | None,
                "error": str | None
            }
        """
        try:
            # 1. Detectar intención
            if not detect_event_intent(message_body):
                return {
                    "success": False,
                    "event": None,
                    "error": "No se detectó intención de crear evento",
                }
            
            # 2. Extraer fecha/hora
            received_at = datetime.now(DEFAULT_TZ)
            start, end = parse_datetime_from_text(message_body, received_at)
            
            if not start:
                return {
                    "success": False,
                    "event": None,
                    "error": "No se pudo extraer fecha/hora del mensaje",
                }
            
            if not end:
                end = start + timedelta(hours=1)
            
            # 3. Extraer título
            title = extract_title_from_message(message_body)
            
            # 4. Construir evento
            event = {
                "title": title,
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
                "timezone": str(start.tzinfo) if start.tzinfo else "UTC",
                "description": f"Mensaje de WhatsApp:\n{message_body}\n\nDe: {from_number}",
            }
            
            logger.info(
                f"✅ Event extracted from WhatsApp message: "
                f"title='{title}', start={start.isoformat()}"
            )
            
            return {
                "success": True,
                "event": event,
                "error": None,
            }
            
        except Exception as e:
            logger.error(f"Error extracting event from WhatsApp message: {e}", exc_info=True)
            return {
                "success": False,
                "event": None,
                "error": str(e),
            }



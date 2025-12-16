# 📱 Flujo de Detección y Creación de Eventos desde WhatsApp

## 🎯 Resumen

Este documento explica el flujo completo de cómo el sistema detecta mensajes de WhatsApp que requieren crear eventos y los crea automáticamente.

## 🔄 Flujo Completo

```
┌─────────────────────────────────────────────────────────────┐
│  1. Usuario envía mensaje por WhatsApp                      │
│     Ejemplo: "Reunión mañana a las 10:00"                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. Twilio recibe mensaje y envía webhook                   │
│     POST /api/v1/whatsapp/webhook                           │
│     Headers: X-Twilio-Signature                             │
│     Body: MessageSid, From, To, Body                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Validación de Seguridad                                 │
│     - Valida firma X-Twilio-Signature                       │
│     - Verifica que viene de Twilio                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Respuesta Inmediata a Twilio                            │
│     {"status": "received"}                                  │
│     (No bloquea, procesa en background)                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  5. Procesamiento en Background                             │
│     process_whatsapp_message()                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────┴───────────────────┐
        │                                       │
        ↓                                       ↓
┌──────────────────────┐          ┌──────────────────────┐
│ 5a. Agent Orchestrator│          │ 5b. WhatsApp Processor│
│     - Detecta intención│          │     - Extrae fecha/hora│
│     - Intenta crear    │          │     - Extrae título    │
│       evento           │          │     - Detecta keywords │
└──────────────────────┘          └──────────────────────┘
        │                                       │
        └───────────────────┬───────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  6. Creación de Evento                                      │
│     - Si Agent creó evento → usar ese                       │
│     - Si no, usar extracción manual                         │
│     - Llamar a calendar_tool.execute()                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  7. Respuesta por WhatsApp                                  │
│     - Si evento creado: confirmación con detalles           │
│     - Si no: respuesta del agente                           │
│     - Enviar vía whatsapp_tool.execute()                    │
└─────────────────────────────────────────────────────────────┘
```

## 📝 Detalles de Implementación

### 1. Endpoint Webhook (`app/api/whatsapp.py`)

**Responsabilidades**:
- Recibe webhook de Twilio
- Valida firma de seguridad
- Inicia procesamiento en background
- Responde inmediatamente a Twilio

**Código clave**:
```python
@router.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    # Validar firma
    # Extraer datos del mensaje
    # Procesar en background
    # Responder inmediatamente
```

### 2. Procesador de Mensajes (`app/services/whatsapp_processor.py`)

**Responsabilidades**:
- Detecta intención de crear evento
- Extrae fecha/hora del mensaje
- Extrae título del mensaje
- Prepara datos para crear evento

**Métodos principales**:
- `detect_event_intent()`: Detecta si el mensaje requiere crear evento
- `parse_datetime_from_text()`: Extrae fecha/hora usando regex
- `extract_title_from_message()`: Extrae título del mensaje
- `extract_event_from_message()`: Método principal que orquesta la extracción

### 3. Detección de Intención

**Estrategia dual**:

#### A. Agent Orchestrator
- Usa el agente para detectar intención
- Si detecta `Intent.CALENDAR` o `Intent.SCHEDULING`
- Intenta crear evento directamente

#### B. WhatsApp Processor
- Busca keywords de eventos: "reunión", "cita", "meeting", etc.
- Busca patrones de fecha/hora
- Si encuentra ambos → intención detectada

### 4. Extracción de Fecha/Hora

**Patrones soportados**:

1. **Fechas relativas**:
   - "mañana a las 10"
   - "hoy a las 15:30"
   - "pasado mañana a las 9"

2. **Días de la semana**:
   - "el lunes a las 14:00"
   - "el viernes de 10 a 12"

3. **Fechas completas**:
   - "15/01/2025 a las 10:00"
   - "2025-01-20 14:30"

4. **Rangos de hora**:
   - "de 9:00 a 11:00"
   - "10-12"

**Implementación**: Usa regex patterns similares a `extract_events_from_messages.py`

### 5. Creación de Evento

**Flujo**:
```python
# Si Agent creó evento → usar ese
if event_created:
    event_details = tool_result["result"]
else:
    # Extraer manualmente
    extraction_result = await message_processor.extract_event_from_message(...)
    # Crear evento
    create_result = await calendar_tool.execute(
        summary=event["title"],
        start_datetime=event["start_at"],
        end_datetime=event["end_at"],
        ...
    )
```

### 6. Respuesta Automática

**Formato de respuesta**:
```
✅ Evento creado exitosamente!

📅 [Título del evento]
🕐 [Fecha y hora]
🔗 Meet: [Link de Google Meet]
📎 Calendario: [Link del evento]
```

## 🧪 Casos de Prueba

### Caso 1: Mensaje Simple
**Input**: "Reunión mañana a las 10:00"
**Output esperado**:
- ✅ Detecta intención
- ✅ Extrae: mañana, 10:00
- ✅ Crea evento
- ✅ Responde confirmación

### Caso 2: Mensaje con Fecha Completa
**Input**: "Agenda una cita el 15/01/2025 a las 14:30"
**Output esperado**:
- ✅ Extrae fecha completa
- ✅ Extrae hora
- ✅ Título: "Agenda una cita"

### Caso 3: Mensaje sin Intención
**Input**: "Hola, ¿cómo estás?"
**Output esperado**:
- ✅ No detecta intención
- ✅ Responde con agente
- ✅ No crea evento

### Caso 4: Mensaje con Rango
**Input**: "Meeting el viernes de 9:00 a 11:00"
**Output esperado**:
- ✅ Extrae día (viernes)
- ✅ Extrae rango (9:00-11:00)
- ✅ Crea evento con duración correcta

## 🔍 Debugging

### Logs Importantes

```
📨 WhatsApp message received: From=+1234567890, Body='...', SID=SM...
🔄 Processing WhatsApp message: SM...
✅ Event extracted from WhatsApp message: title='...', start=...
✅ WhatsApp response sent to +1234567890
```

### Verificar en Supabase

```sql
-- Ver eventos creados desde WhatsApp
SELECT * FROM extracted_events 
WHERE source = 'whatsapp' 
ORDER BY created_at DESC;

-- Ver eventos en Google Calendar
SELECT * FROM calendar_events 
WHERE source = 'whatsapp'
ORDER BY start_at DESC;
```

## ⚠️ Limitaciones Actuales

1. **Extracción básica**: Usa regex, no LLM para extracción compleja
2. **Un evento por mensaje**: Solo extrae un evento por mensaje
3. **Sin confirmación**: Crea evento directamente, sin pedir confirmación
4. **Timezone fijo**: Usa UTC por defecto (se puede mejorar)

## 🚀 Mejoras Futuras

1. **LLM para extracción**: Usar LLM para extraer información más compleja
2. **Múltiples eventos**: Detectar múltiples eventos en un mensaje
3. **Confirmación interactiva**: Pedir confirmación antes de crear
4. **Ubicación**: Extraer ubicación del mensaje
5. **Participantes**: Detectar participantes mencionados
6. **Recordatorios**: Configurar recordatorios automáticos

## 📚 Archivos Relacionados

- `app/api/whatsapp.py`: Endpoint webhook
- `app/services/whatsapp_processor.py`: Procesador de mensajes
- `app/agents/tools/whatsapp_tool.py`: Tool para enviar mensajes
- `app/agents/tools/calendar_tool.py`: Tool para crear eventos
- `scripts/extract_events_from_messages.py`: Script de extracción (referencia)


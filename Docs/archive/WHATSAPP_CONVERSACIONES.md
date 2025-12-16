# 📱 Procesamiento de Conversaciones de WhatsApp

## 🎯 Objetivo

Crear un sistema que:
1. **Almacene todas las conversaciones** de WhatsApp en Supabase
2. **Procese conversaciones completas** (no solo mensajes individuales)
3. **Detecte eventos automáticamente** usando el contexto de la conversación
4. **Cree eventos** cuando se detecten en el contexto conversacional

## 🔍 Limitaciones de Twilio

### ❌ Lo que NO puede hacer Twilio:
- **Leer conversaciones históricas**: No hay API para obtener mensajes pasados
- **Acceder a mensajes antiguos**: Solo puede recibir mensajes nuevos vía webhooks
- **Leer mensajes de otros usuarios**: Solo recibe mensajes enviados a tu número

### ✅ Lo que SÍ puede hacer Twilio:
- **Recibir mensajes en tiempo real** vía webhooks
- **Almacenar mensajes** que recibes
- **Procesar mensajes** según llegan
- **Mantener contexto** de conversaciones almacenando en base de datos

## 🏗️ Solución Propuesta

### Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│  1. Mensaje llega por WhatsApp                               │
│     → Webhook Twilio → /api/v1/whatsapp/webhook            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. Almacenar Mensaje en Supabase                           │
│     Tabla: whatsapp_messages                                │
│     - message_sid, from_number, body, timestamp             │
│     - conversation_id (agrupa por contacto)                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Obtener Contexto de Conversación                        │
│     - Buscar últimos N mensajes del mismo contacto          │
│     - Construir historial conversacional                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Procesar con Agente (Contexto Completo)                 │
│     - Agent Orchestrator con historial                      │
│     - Detecta intención usando contexto completo            │
│     - Extrae eventos del contexto conversacional            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  5. Detectar y Crear Eventos                                │
│     - Si se detecta evento → crear en Google Calendar       │
│     - Marcar mensajes procesados                            │
│     - Responder confirmación                                │
└─────────────────────────────────────────────────────────────┘
```

## 📊 Base de Datos

### Tabla: `whatsapp_messages`

```sql
CREATE TABLE IF NOT EXISTS whatsapp_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_sid TEXT UNIQUE NOT NULL,  -- SID de Twilio
    conversation_id TEXT NOT NULL,     -- Agrupa por from_number
    from_number TEXT NOT NULL,
    to_number TEXT NOT NULL,
    body TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,   -- Si ya se procesó para eventos
    event_extracted BOOLEAN DEFAULT FALSE,  -- Si se extrajo evento
    event_id UUID REFERENCES extracted_events(id),  -- Evento relacionado
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_whatsapp_messages_conversation ON whatsapp_messages(conversation_id, received_at DESC);
CREATE INDEX idx_whatsapp_messages_processed ON whatsapp_messages(processed, received_at DESC);
```

### Tabla: `whatsapp_conversations` (Opcional)

```sql
CREATE TABLE IF NOT EXISTS whatsapp_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id TEXT UNIQUE NOT NULL,  -- from_number
    contact_name TEXT,  -- Nombre del contacto (si está disponible)
    last_message_at TIMESTAMPTZ,
    event_count INTEGER DEFAULT 0,  -- Eventos extraídos de esta conversación
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 🔄 Flujo de Procesamiento

### Opción A: Procesamiento en Tiempo Real

Cada mensaje se procesa inmediatamente con el contexto de la conversación:

```python
async def process_whatsapp_message_with_context(
    message_sid: str,
    from_number: str,
    message_body: str,
):
    # 1. Almacenar mensaje
    await store_whatsapp_message(...)
    
    # 2. Obtener contexto (últimos 10 mensajes)
    conversation_context = await get_conversation_context(from_number, limit=10)
    
    # 3. Construir historial para el agente
    chat_history = build_chat_history(conversation_context)
    
    # 4. Procesar con agente (con contexto)
    result = await agent_orchestrator.run(
        query=message_body,
        chat_history=chat_history,  # ← Contexto completo
    )
    
    # 5. Detectar eventos del resultado
    if event_detected(result):
        create_event(...)
```

### Opción B: Procesamiento Periódico (Batch)

Procesa conversaciones completas periódicamente:

```python
async def process_conversations_batch():
    # 1. Obtener conversaciones no procesadas
    conversations = await get_unprocessed_conversations()
    
    for conversation_id in conversations:
        # 2. Obtener todos los mensajes de la conversación
        messages = await get_conversation_messages(conversation_id)
        
        # 3. Construir contexto completo
        full_context = build_full_context(messages)
        
        # 4. Procesar con agente
        result = await agent_orchestrator.run(
            query="Analiza esta conversación y extrae eventos mencionados",
            chat_history=full_context,
        )
        
        # 5. Extraer eventos
        events = extract_events_from_result(result)
        for event in events:
            create_event(event)
```

## 🚀 Implementación Recomendada

### Híbrida: Tiempo Real + Batch

1. **Tiempo Real**: Procesa mensajes nuevos inmediatamente
2. **Batch**: Revisa conversaciones completas periódicamente para detectar eventos que se mencionaron en múltiples mensajes

## 📝 Ejemplo de Conversación

```
Usuario: "Hola, ¿estás disponible?"
Bot: "Sí, ¿en qué puedo ayudarte?"
Usuario: "Quiero agendar una reunión"
Bot: "Claro, ¿cuándo te gustaría?"
Usuario: "El viernes a las 10"
Bot: "Perfecto, ¿sobre qué tema?"
Usuario: "Revisión del proyecto"
```

**Procesamiento**:
- Mensaje 1-2: No hay evento
- Mensaje 3: Detecta intención de agendar
- Mensaje 4: Extrae día (viernes)
- Mensaje 5: Extrae hora (10)
- Mensaje 6: Extrae tema (revisión del proyecto)

**Resultado**: Crea evento "Revisión del proyecto" el viernes a las 10:00

## 🔧 Alternativas Nativas

### 1. WhatsApp Business API (Meta)

**Ventajas**:
- ✅ API oficial de Meta
- ✅ Webhooks nativos
- ✅ Puede leer mensajes (con limitaciones)
- ✅ Mejor integración

**Desventajas**:
- ❌ Requiere aprobación de Meta
- ❌ Proceso de verificación más complejo
- ❌ Puede ser más costoso

**Documentación**: https://developers.facebook.com/docs/whatsapp

### 2. WhatsApp Cloud API

**Ventajas**:
- ✅ API más reciente
- ✅ Webhooks mejorados
- ✅ Mejor para aplicaciones empresariales

**Desventajas**:
- ❌ Requiere cuenta de negocio verificada
- ❌ Proceso de setup más complejo

### 3. Twilio Conversations API

**Ventajas**:
- ✅ Gestiona conversaciones completas
- ✅ Historial de mensajes
- ✅ Mejor que solo webhooks básicos

**Desventajas**:
- ❌ Aún requiere webhooks para recibir mensajes
- ❌ No puede leer mensajes históricos previos

## 💡 Recomendación

**Usar Twilio con almacenamiento propio**:
1. ✅ Ya está implementado
2. ✅ Funciona bien para tiempo real
3. ✅ Almacenar en Supabase permite análisis completo
4. ✅ Procesar conversaciones completas con contexto
5. ✅ Más flexible que APIs nativas

**Mejora futura**: Migrar a WhatsApp Business API si necesitas más funcionalidades.

---

## ✅ Implementación Actual

### Archivos Creados

1. **`app/services/whatsapp_conversation.py`**
   - `WhatsAppConversationService`: Gestiona almacenamiento y contexto
   - `store_message()`: Almacena mensajes en Supabase
   - `get_conversation_context()`: Obtiene últimos N mensajes
   - `build_chat_history()`: Construye historial para el agente
   - `mark_message_processed()`: Marca mensajes como procesados

2. **`app/api/whatsapp_batch.py`**
   - `process_conversations_batch()`: Procesa conversaciones en batch
   - `get_conversation_messages()`: Obtiene mensajes de una conversación
   - `list_conversations()`: Lista todas las conversaciones

3. **`sql/whatsapp_messages.sql`**
   - Tabla `whatsapp_messages`: Almacena todos los mensajes
   - Tabla `whatsapp_conversations`: Gestiona estadísticas de conversaciones
   - Triggers automáticos para actualizar estadísticas

### Flujo Implementado

```
Mensaje llega → Almacenar en Supabase → Obtener contexto → 
Procesar con agente (contexto completo) → Detectar evento → 
Crear evento → Marcar procesado → Responder
```

### Endpoints Disponibles

- `POST /api/v1/whatsapp/webhook` - Recibe mensajes (ya existía, ahora almacena)
- `POST /api/v1/whatsapp/process-conversations` - Procesa conversaciones en batch
- `GET /api/v1/whatsapp/conversations` - Lista conversaciones
- `GET /api/v1/whatsapp/conversations/{id}/messages` - Obtiene mensajes de una conversación

### Próximos Pasos

1. **Ejecutar SQL**: Ejecutar `sql/whatsapp_messages.sql` en Supabase
2. **Probar webhook**: Enviar mensaje de prueba
3. **Verificar almacenamiento**: Revisar en Supabase que se almacenaron mensajes
4. **Probar batch processing**: Llamar a `/api/v1/whatsapp/process-conversations`


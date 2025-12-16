# WhatsApp Webhook - Guía de Configuración y Pruebas

Esta guía explica cómo configurar y probar el webhook de WhatsApp para detectar y crear eventos automáticamente.

## 🎯 Funcionalidad

El sistema puede:
1. **Recibir mensajes de WhatsApp** vía webhook de Twilio
2. **Detectar intención** de crear un evento (usando el agente)
3. **Extraer información** del evento (fecha, hora, título) del mensaje
4. **Crear el evento** automáticamente en Google Calendar
5. **Responder por WhatsApp** confirmando el evento creado

## 📋 Prerrequisitos

1. **Cuenta de Twilio** con WhatsApp habilitado
2. **Número de WhatsApp** configurado en Twilio
3. **Credenciales de Twilio** configuradas en `.env`
4. **Google Calendar** configurado (OAuth)
5. **URL pública** para el webhook (usar ngrok para desarrollo)

## ⚙️ Configuración

### 1. Variables de Entorno

Añade a tu `.env`:

```env
# Twilio WhatsApp
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886  # Tu número de Twilio WhatsApp
```

### 2. Instalar Dependencias

```bash
pip install twilio>=8.10.0
```

O reinstalar todas las dependencias:

```bash
pip install -r requirements.txt
```

### 3. Configurar Webhook en Twilio

#### Opción A: Usando ngrok (Desarrollo)

1. **Iniciar ngrok**:
```bash
ngrok http 8000
```

2. **Copiar la URL pública** (ej: `https://abc123.ngrok.io`)

3. **Configurar webhook en Twilio Console**:
   - Ve a [Twilio Console](https://console.twilio.com/)
   - Navega a **Messaging > Settings > WhatsApp Sandbox** (o tu número de WhatsApp)
   - En **"When a message comes in"**, configura:
     - URL: `https://tu-ngrok-url.ngrok.io/api/v1/whatsapp/webhook`
     - Método: `POST`

#### Opción B: Usando Twilio CLI

```bash
# Instalar Twilio CLI si no lo tienes
npm install -g twilio-cli

# Configurar credenciales
twilio login

# Configurar webhook
twilio api:core:incoming-phone-numbers:update \
  --sid PNxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
  --sms-url "https://tu-url.com/api/v1/whatsapp/webhook" \
  --sms-method POST
```

### 4. Verificar Configuración

El endpoint está disponible en:
```
POST /api/v1/whatsapp/webhook
```

## 🧪 Pruebas

### Prueba 1: Mensaje Simple con Fecha/Hora

Envía un mensaje de WhatsApp a tu número de Twilio:

```
Reunión mañana a las 10:00
```

**Resultado esperado**:
- ✅ El sistema detecta la intención de crear evento
- ✅ Extrae: fecha (mañana), hora (10:00)
- ✅ Crea evento en Google Calendar
- ✅ Responde por WhatsApp: "✅ Evento creado exitosamente! 📅 Reunión mañana..."

### Prueba 2: Mensaje con Fecha Completa

```
Agenda una cita el 15/01/2025 a las 14:30
```

**Resultado esperado**:
- ✅ Extrae fecha completa y hora
- ✅ Crea evento con título "Agenda una cita"
- ✅ Responde con confirmación

### Prueba 3: Mensaje con Rango de Horas

```
Meeting el viernes de 9:00 a 11:00
```

**Resultado esperado**:
- ✅ Extrae día (viernes), hora inicio (9:00), hora fin (11:00)
- ✅ Crea evento con duración correcta

### Prueba 4: Mensaje sin Intención de Evento

```
Hola, ¿cómo estás?
```

**Resultado esperado**:
- ✅ El sistema responde con la respuesta del agente
- ✅ No crea evento (no se detectó intención)

## 🔍 Flujo de Procesamiento

```
1. Usuario envía mensaje por WhatsApp
   ↓
2. Twilio recibe mensaje y envía webhook a /api/v1/whatsapp/webhook
   ↓
3. Validación de firma de Twilio (X-Twilio-Signature)
   ↓
4. Procesamiento en background:
   a. Agent Orchestrator detecta intención
   b. Si detecta calendar/scheduling → intenta crear evento
   c. Si no, WhatsAppMessageProcessor extrae evento del mensaje
   d. Si se extrae evento → crea en Google Calendar
   ↓
5. Respuesta automática por WhatsApp:
   - Si evento creado: confirmación con detalles
   - Si no: respuesta del agente
```

## 📝 Formatos de Mensaje Soportados

El sistema puede extraer eventos de mensajes como:

### Fechas Relativas
- "Reunión mañana a las 10"
- "Cita hoy a las 15:30"
- "Meeting pasado mañana a las 9"

### Días de la Semana
- "Reunión el lunes a las 14:00"
- "Cita el viernes de 10 a 12"
- "Meeting el miércoles a las 9:30"

### Fechas Completas
- "Agenda el 15/01/2025 a las 10:00"
- "Reunión 2025-01-20 14:30"
- "Cita el 20/01/25 a las 16:00"

### Rangos de Hora
- "Meeting de 9:00 a 11:00"
- "Reunión el lunes de 14:30 a 16:00"
- "Cita mañana 10-12"

### Keywords que Activan Detección
- "reunión", "reunion", "meeting"
- "cita", "appointment"
- "agenda", "agendar", "programar", "schedule"
- "evento", "event", "conferencia", "conference"
- "llamada", "call", "videollamada"
- "presentación", "presentation"

## 🐛 Troubleshooting

### Error: "Invalid Twilio signature"

**Causa**: La firma de Twilio no coincide.

**Solución**:
- Verifica que `TWILIO_AUTH_TOKEN` esté correcto
- Asegúrate de que la URL del webhook sea exactamente la misma en Twilio
- Si estás usando ngrok, verifica que la URL sea HTTPS

### Error: "TWILIO_AUTH_TOKEN not configured"

**Causa**: Falta la variable de entorno.

**Solución**:
- Añade `TWILIO_AUTH_TOKEN` a tu `.env`
- Reinicia el servidor

### No se reciben mensajes

**Causa**: Webhook no configurado o URL incorrecta.

**Solución**:
- Verifica que el webhook esté configurado en Twilio Console
- Verifica que ngrok esté corriendo (si usas ngrok)
- Revisa los logs del servidor para ver si llegan requests

### Evento no se crea automáticamente

**Causa**: No se detectó intención o no se pudo extraer fecha/hora.

**Solución**:
- Verifica que el mensaje tenga keywords de eventos Y fecha/hora
- Revisa los logs para ver qué detectó el sistema
- Prueba con un formato más explícito: "Reunión mañana a las 10:00"

### No se envía respuesta por WhatsApp

**Causa**: Error al enviar mensaje o credenciales incorrectas.

**Solución**:
- Verifica `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`
- Revisa los logs para ver el error específico
- Verifica que el número `TWILIO_WHATSAPP_FROM` esté en formato `whatsapp:+1234567890`

## 📊 Logs

El sistema registra información detallada:

```
📨 WhatsApp message received: From=+1234567890, Body='Reunión mañana...', SID=SM...
🔄 Processing WhatsApp message: SM...
✅ Event extracted from WhatsApp message: title='Reunión mañana', start=2025-01-16T10:00:00+00:00
✅ WhatsApp response sent to +1234567890
```

## 🔒 Seguridad

- ✅ **Validación de firma**: El webhook valida la firma de Twilio para asegurar que viene de Twilio
- ✅ **HTTPS requerido**: Usa HTTPS en producción (ngrok lo proporciona en desarrollo)
- ✅ **Background processing**: El procesamiento se hace en background para responder rápido a Twilio

## 🚀 Próximos Pasos

1. **Mejorar extracción**: Usar LLM para extraer información más compleja
2. **Soporte de ubicación**: Extraer ubicación del mensaje
3. **Confirmación interactiva**: Permitir confirmar/cancelar antes de crear
4. **Múltiples eventos**: Detectar múltiples eventos en un solo mensaje
5. **Recordatorios**: Configurar recordatorios automáticos

## 📚 Referencias

- [Twilio WhatsApp API](https://www.twilio.com/docs/whatsapp)
- [Twilio Webhook Security](https://www.twilio.com/docs/usage/webhooks/webhooks-security)
- [Twilio Request Validator](https://www.twilio.com/docs/usage/webhooks/webhooks-security#validating-requests)


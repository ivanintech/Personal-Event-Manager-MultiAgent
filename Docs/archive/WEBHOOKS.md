# Webhooks - Guía de Configuración y Pruebas

Esta guía explica cómo configurar y probar los webhooks de Calendly.

## Webhook de Calendly

### Configuración

1. **Obtener URL pública con ngrok:**
   ```bash
   # Instalar ngrok si no lo tienes
   # https://ngrok.com/download
   
   # Exponer puerto 8000
   ngrok http 8000
   ```

2. **Configurar webhook secret en `.env`:**
   ```env
   CALENDLY_WEBHOOK_SECRET=tu_secret_aqui
   ```

3. **Registrar webhook en Calendly:**
   ```bash
   python scripts/register_calendly_webhook.py
   ```
   
   O manualmente desde la UI de Calendly:
   - Ve a Settings > Integrations > Webhooks
   - Añade webhook con URL: `https://tu-ngrok-url.ngrok.io/api/v1/calendly/webhook`
   - Selecciona eventos: `invitee.created`, `invitee.canceled`
   - Configura el secret (debe coincidir con `CALENDLY_WEBHOOK_SECRET`)

### Endpoint

**POST** `/api/v1/calendly/webhook`

**Headers requeridos:**
- `Content-Type: application/json`
- `Calendly-Webhook-Signature: <hmac_sha256_signature>`

**Validación HMAC:**
El endpoint valida la firma HMAC usando `CALENDLY_WEBHOOK_SECRET` para asegurar que el webhook viene de Calendly.

**Eventos soportados:**
- `invitee.created`: Cuando se crea una nueva cita
- `invitee.canceled`: Cuando se cancela una cita

### Pruebas

#### Opción 1: Usar script helper
```bash
# Editar scripts/test_webhook_calendly.py con tu NGROK_URL y WEBHOOK_SECRET
python scripts/test_webhook_calendly.py
```

#### Opción 2: Usar curl
```bash
# Generar firma HMAC (requiere Python o herramienta similar)
PAYLOAD='{"event":"invitee.created",...}'
SECRET="tu_secret"
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

curl -X POST https://tu-ngrok-url.ngrok.io/api/v1/calendly/webhook \
  -H "Content-Type: application/json" \
  -H "Calendly-Webhook-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

#### Opción 3: Desde Calendly UI
1. Crea un evento de prueba en Calendly
2. Programa una cita
3. El webhook debería recibir el evento `invitee.created`
4. Cancela la cita
5. El webhook debería recibir el evento `invitee.canceled`

### Verificación

Después de recibir un webhook:
1. Verifica en Supabase que el evento se insertó en `extracted_events` con `source='calendly'`
2. Revisa los logs del servidor para confirmar que el webhook se procesó correctamente
3. Usa el endpoint `/api/v1/calendly/events` para listar eventos y verificar

### Troubleshooting

**Error 401 Unauthorized:**
- Verifica que `CALENDLY_WEBHOOK_SECRET` coincida con el secret configurado en Calendly
- Verifica que la firma HMAC se genere correctamente

**Error 500 Internal Server Error:**
- Revisa los logs del servidor
- Verifica que Supabase esté configurado correctamente
- Verifica que el token OAuth de Calendly esté válido

**Webhook no se recibe:**
- Verifica que ngrok esté corriendo y la URL sea accesible
- Verifica que el webhook esté registrado en Calendly
- Revisa los logs de ngrok para ver si hay requests entrantes

## Futuros Webhooks

### Gmail/IMAP (Planeado)
Cuando se implemente, seguirá un patrón similar:
- Endpoint: `/api/v1/gmail/webhook` o `/api/v1/imap/webhook`
- Validación: OAuth token o firma similar
- Eventos: `email.received`, `email.sent`

### WhatsApp (Planeado)
Si se implementa con Twilio:
- Endpoint: `/api/v1/whatsapp/webhook`
- Validación: Twilio signature
- Eventos: `message.received`, `message.sent`


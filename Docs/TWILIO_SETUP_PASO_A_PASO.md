# 🔧 Configuración de Twilio WhatsApp - Guía Paso a Paso

## 📋 Credenciales Necesarias

Para que funcione el sistema, necesitas estas 3 credenciales:

1. **TWILIO_ACCOUNT_SID** - ID de tu cuenta
2. **TWILIO_AUTH_TOKEN** - Token de autenticación
3. **TWILIO_WHATSAPP_FROM** - Número de WhatsApp de Twilio

---

## 🎯 Paso 1: Obtener Account SID

**Ya lo tienes visible en la pantalla actual:**

En el código Python que ves a la derecha, busca:
```python
account_sid = 'AC_YOUR_ACCOUNT_SID'
```

**Tu Account SID es**: `AC_YOUR_ACCOUNT_SID`

✅ **Copia este valor** - lo necesitarás para `.env`

---

## 🔑 Paso 2: Obtener Auth Token

El Auth Token está oculto por seguridad. Para verlo:

1. **En la pantalla actual**, busca el checkbox **"Show auth token"** (arriba a la derecha del panel de código)
2. **Marca el checkbox** para mostrar el token
3. **Copia el valor** que aparece en lugar de `[AuthToken]`

**Alternativa si no está visible**:
1. Ve al **Dashboard principal** de Twilio (icono de casa en el sidebar izquierdo)
2. En la página principal verás un panel con tus credenciales
3. Haz clic en **"Show"** o **"Reveal"** junto a "Auth Token"
4. **Copia el token** (es sensible, no lo compartas)

✅ **Copia este valor** - lo necesitarás para `.env`

---

## 📱 Paso 3: Obtener Número de WhatsApp (From)

**Ya lo tienes visible en la pantalla actual:**

En el campo **"From"** del formulario, verás:
```
whatsapp:+1415523886
```

**Tu número de WhatsApp es**: `+1415523886` (o el que aparezca en tu pantalla)

**Nota**: En `.env` puedes usar solo el número `+1415523886` o con el prefijo `whatsapp:+1415523886` (ambos funcionan)

✅ **Copia este valor** - lo necesitarás para `.env`

---

## ⚙️ Paso 4: Configurar Variables de Entorno

Abre tu archivo `.env` y añade estas líneas:

```env
# Twilio WhatsApp Credentials
TWILIO_ACCOUNT_SID=AC_YOUR_ACCOUNT_SID
TWILIO_AUTH_TOKEN=tu_auth_token_aqui
TWILIO_WHATSAPP_FROM=+1415523886
```

**Reemplaza**:
- `AC_YOUR_ACCOUNT_SID` con tu Account SID real
- `tu_auth_token_aqui` con tu Auth Token real
- `+1415523886` con tu número de WhatsApp real

---

## 🔗 Paso 5: Configurar Webhook para Recibir Mensajes

Para que el sistema pueda **recibir mensajes** de WhatsApp, necesitas configurar un webhook:

### Opción A: Usando ngrok (Desarrollo Local)

1. **Instala ngrok** si no lo tienes:
   ```bash
   # Windows (con Chocolatey)
   choco install ngrok
   
   # O descarga desde: https://ngrok.com/download
   ```

2. **Inicia tu servidor FastAPI**:
   ```bash
   python start_server.py
   # O
   uvicorn main:app --reload --port 8000
   ```

3. **En otra terminal, inicia ngrok**:
   ```bash
   ngrok http 8000
   ```

4. **Copia la URL HTTPS** que ngrok te da:
   ```
   https://abc123.ngrok.io
   ```

5. **En Twilio Console**:
   - Ve a **Messaging** → **Settings** → **WhatsApp Sandbox**
   - O desde la pantalla actual, haz clic en **"Sandbox settings"** (tab arriba)
   - Busca **"When a message comes in"**
   - Pega tu URL: `https://tu-ngrok-url.ngrok.io/api/v1/whatsapp/webhook`
   - Método: **POST**
   - Guarda los cambios

### Opción B: Usando URL Pública (Producción)

Si tienes un servidor desplegado (Railway, Render, etc.):

1. **Copia la URL pública** de tu servidor
2. **En Twilio Console**:
   - Ve a **Messaging** → **Settings** → **WhatsApp Sandbox**
   - En **"When a message comes in"**, configura:
     - URL: `https://tu-servidor.com/api/v1/whatsapp/webhook`
     - Método: **POST**
   - Guarda los cambios

---

## ✅ Paso 6: Verificar Configuración

### 1. Verificar Credenciales

Crea un script de prueba (`test_twilio_credentials.py`):

```python
import os
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM")

print(f"Account SID: {account_sid}")
print(f"Auth Token: {'✅ Configurado' if auth_token else '❌ Faltante'}")
print(f"WhatsApp From: {whatsapp_from}")

if account_sid and auth_token:
    try:
        client = Client(account_sid, auth_token)
        # Intentar obtener información de la cuenta
        account = client.api.accounts(account_sid).fetch()
        print(f"✅ Credenciales válidas - Cuenta: {account.friendly_name}")
    except Exception as e:
        print(f"❌ Error: {e}")
else:
    print("❌ Faltan credenciales en .env")
```

Ejecuta:
```bash
python test_twilio_credentials.py
```

### 2. Probar Envío de Mensaje

Desde la pantalla actual de Twilio:
1. Llena el formulario:
   - **To**: Tu número de WhatsApp personal (debe estar en el sandbox)
   - **From**: Ya está configurado
   - **Content Template**: Elige uno
2. Haz clic en **"Send template message"**
3. Deberías recibir el mensaje en tu WhatsApp

### 3. Probar Webhook (Recibir Mensajes)

1. **Envía un mensaje** desde tu WhatsApp personal al número de Twilio
2. **Verifica los logs** de tu servidor:
   ```bash
   # Deberías ver:
   📨 WhatsApp message received: From=+34642473452, Body='...', SID=SM...
   ```
3. **Verifica en Supabase** que el mensaje se almacenó:
   ```sql
   SELECT * FROM whatsapp_messages ORDER BY received_at DESC LIMIT 5;
   ```

---

## 🎯 Resumen de Credenciales

| Credencial | Dónde Encontrarla | Ejemplo |
|------------|-------------------|---------|
| **TWILIO_ACCOUNT_SID** | Panel de código Python (visible) | `AC_YOUR_ACCOUNT_SID` |
| **TWILIO_AUTH_TOKEN** | Checkbox "Show auth token" o Dashboard | `tu_token_secreto_aqui` |
| **TWILIO_WHATSAPP_FROM** | Campo "From" del formulario | `+1415523886` |

---

## 🐛 Troubleshooting

### Error: "TWILIO_AUTH_TOKEN not configured"

**Solución**: 
- Verifica que el token esté en `.env`
- Asegúrate de copiar el token completo (puede ser largo)
- Reinicia el servidor después de cambiar `.env`

### Error: "Invalid Twilio signature"

**Solución**:
- Verifica que `TWILIO_AUTH_TOKEN` sea correcto
- Asegúrate de que la URL del webhook sea exactamente la misma en Twilio
- Si usas ngrok, verifica que la URL sea HTTPS

### No se reciben mensajes

**Solución**:
1. Verifica que el webhook esté configurado en Twilio
2. Verifica que ngrok esté corriendo (si usas desarrollo local)
3. Verifica que tu número esté en el sandbox de Twilio
4. Revisa los logs del servidor para ver si llegan requests

### Sandbox de Twilio

**Importante**: Estás usando el **Sandbox de Twilio**, que tiene limitaciones:

- ✅ Puedes enviar mensajes a números que estén en el sandbox
- ✅ Puedes recibir mensajes de números en el sandbox
- ❌ No puedes enviar a números fuera del sandbox (sin aprobación)

**Para añadir un número al sandbox**:
1. En la pantalla actual, busca el código para unirte al sandbox
2. Envía ese código desde tu WhatsApp al número de Twilio
3. Tu número quedará registrado en el sandbox

---

## 🚀 Siguiente Paso

Una vez configuradas las credenciales:

1. ✅ Ejecuta el SQL: `sql/whatsapp_messages.sql` en Supabase
2. ✅ Reinicia el servidor: `python start_server.py`
3. ✅ Prueba enviando un mensaje desde tu WhatsApp
4. ✅ Verifica que se procese y cree eventos automáticamente

---

## 📚 Referencias

- [Twilio WhatsApp Sandbox](https://www.twilio.com/docs/whatsapp/sandbox)
- [Twilio Console](https://console.twilio.com/)
- [Documentación WhatsApp Webhook](https://www.twilio.com/docs/whatsapp/webhook)



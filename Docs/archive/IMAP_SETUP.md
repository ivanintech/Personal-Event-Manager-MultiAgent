# Configuración IMAP (Thunderbird/Outlook/Gmail IMAP)

## Estado

✅ **Implementado**: Cliente MCP IMAP, tools de búsqueda/lectura, integración con EmailAgent

## Configuración

Añade estas variables a tu `.env`:

```env
# IMAP (para leer emails)
IMAP_HOST=imap.gmail.com          # o imap-mail.outlook.com, imap.thunderbird.net, etc.
IMAP_PORT=993                      # 993 para SSL, 143 para STARTTLS
IMAP_USER=tu-email@example.com
IMAP_PASS=tu-contraseña-app        # Para Gmail: usar App Password
IMAP_USE_SSL=true                  # true para puerto 993, false para 143
```

### Proveedores Comunes

#### Gmail
```env
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USE_SSL=true
# Nota: Necesitas App Password si tienes 2FA activado
```

#### Outlook/Hotmail
```env
IMAP_HOST=outlook.office365.com
IMAP_PORT=993
IMAP_USE_SSL=true
```

#### Thunderbird (cualquier servidor IMAP)
```env
IMAP_HOST=tu-servidor-imap.com
IMAP_PORT=993
IMAP_USE_SSL=true
```

## Tools Disponibles

### `search_emails`
Busca emails en una carpeta.

**Parámetros**:
- `query`: Criterio IMAP (ejemplos):
  - `"ALL"` - Todos los emails
  - `"UNSEEN"` - No leídos
  - `"FROM user@example.com"` - De un remitente
  - `"SUBJECT texto"` - Con texto en asunto
  - `"SINCE 01-Jan-2025"` - Desde una fecha
  - `"BEFORE 31-Dec-2025"` - Antes de una fecha
- `folder`: Carpeta IMAP (default: `"INBOX"`)
- `max_results`: Máximo de resultados (default: 10)

**Ejemplo**:
```python
result = await execute_tool(
    "search_emails",
    query="UNSEEN",
    folder="INBOX",
    max_results=5
)
```

### `read_email`
Lee un email específico.

**Parámetros**:
- `email_id`: ID del email (obtenido de `search_emails`)
- `folder`: Carpeta IMAP (default: `"INBOX"`)

**Ejemplo**:
```python
result = await execute_tool(
    "read_email",
    email_id="12345",
    folder="INBOX"
)
```

## Uso en EmailAgent

```python
from app.agents.specialists.email_agent import EmailAgent

agent = EmailAgent()

# Buscar emails no leídos
result = await agent.search_emails(query="UNSEEN", max_results=10)

# Leer un email específico
email = await agent.read_email(email_id="12345")
```

## Integración MCP

El cliente IMAP se usa automáticamente cuando:
- `USE_MOCK_MCP=false`
- Configuración IMAP está completa
- Se llama a `search_emails` o `read_email`

Si MCP falla, hay fallback al registry local.

## Troubleshooting

### Error: "IMAP config incompleta"
- Verifica que todas las variables IMAP_* estén configuradas
- Revisa que las credenciales sean correctas

### Error: "Authentication failed"
- Gmail: Usa App Password si tienes 2FA
- Outlook: Verifica que IMAP esté habilitado en tu cuenta
- Verifica usuario/contraseña

### Error: "Connection refused"
- Verifica IMAP_HOST e IMAP_PORT
- Asegúrate de que el servidor IMAP esté accesible
- Revisa firewall/red

## Próximos Pasos

- [ ] Añadir soporte para attachments
- [ ] Añadir soporte para marcar como leído/no leído
- [ ] Añadir soporte para mover emails entre carpetas
- [ ] Tests E2E para IMAP


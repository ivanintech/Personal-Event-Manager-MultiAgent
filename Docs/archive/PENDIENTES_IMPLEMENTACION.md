# Pendientes de Implementación

**Última actualización**: Diciembre 2025

## Estado Actual

### ✅ Implementado

1. **WhatsApp** ✅
   - Cliente MCP Twilio HTTP (`app/mcp/clients/twilio_http.py`)
   - Tool `send_whatsapp_message` registrado
   - MCP server config en `mcp_servers.json`
   - Mapping en `mapping.json`

2. **Email SMTP (Genérico)** ✅
   - Tool `send_email` vía SMTP (funciona con Gmail/Outlook/Thunderbird)
   - Configuración en settings (SMTP_HOST, SMTP_PORT, etc.)
   - Endpoint `/api/v1/email/send`

3. **Gmail MCP** ⚠️ Parcial
   - MCP server config en `mcp_servers.json`
   - Mapping en `mapping.json`
   - ❌ Falta: Cliente MCP real (solo mock)
   - ❌ Falta: Tools para leer/buscar emails

### ❌ Faltante

1. **IMAP (Thunderbird/Outlook)** ❌
   - ❌ MCP server config
   - ❌ Cliente MCP IMAP
   - ❌ Tools para leer/buscar emails vía IMAP
   - ❌ Integración con EmailAgent

2. **Outlook específico (Microsoft Graph)** ❌
   - ❌ MCP server config
   - ❌ Cliente MCP Microsoft Graph
   - ❌ OAuth para Microsoft
   - ❌ Tools para Calendar + Email

3. **EmailAgent completo** ⚠️ Parcial
   - ✅ `send_email` implementado
   - ❌ `search_emails` no implementado (TODO en código)
   - ❌ `read_email` no implementado

## Plan de Implementación

### Prioridad 1: IMAP (Thunderbird/Outlook)

**Objetivo**: Leer y buscar emails vía IMAP

**Archivos a crear/modificar**:
1. `app/mcp/clients/imap_client.py` - Cliente IMAP MCP
2. `app/agents/tools/imap_search_tool.py` - Tool para buscar emails
3. `app/agents/tools/imap_read_tool.py` - Tool para leer emails
4. `app/mcp/mcp_servers.json` - Añadir servidor IMAP
5. `app/mcp/mapping.json` - Mapear tools IMAP
6. `app/config/settings.py` - Añadir config IMAP (IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASS)
7. `app/agents/specialists/email_agent.py` - Implementar `search_emails` y `read_email`

### Prioridad 2: Outlook (Microsoft Graph)

**Objetivo**: Integración completa con Outlook vía Microsoft Graph API

**Archivos a crear/modificar**:
1. `app/mcp/clients/outlook_client.py` - Cliente Microsoft Graph
2. `app/mcp/mcp_servers.json` - Añadir servidor Outlook
3. `app/config/settings.py` - Añadir config Microsoft (MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, etc.)
4. OAuth flow para Microsoft (similar a Google)

### Prioridad 3: Completar EmailAgent

**Objetivo**: Implementar todas las funciones del EmailAgent

**Tareas**:
1. Implementar `search_emails` usando IMAP o Gmail API
2. Implementar `read_email` usando IMAP o Gmail API
3. Añadir soporte para attachments
4. Añadir soporte para CC/BCC en `send_email`

## Recursos de VibeVoice

Del código de `VibeVoice/demo/web/` podemos usar:
- ✅ Patrón de WebSocket streaming (ya implementado)
- ✅ Manejo de logs estructurados (ya implementado)
- ✅ Lock para requests concurrentes (ya implementado)

## Próximos Pasos

1. **Implementar IMAP client y tools** (Prioridad 1)
2. **Completar EmailAgent** con funciones de búsqueda/lectura
3. **Añadir tests E2E** para IMAP
4. **Documentar** configuración IMAP/Outlook


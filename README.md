# 🤖 Personal Coordination Voice Agent

Un agente de coordinación personal con capacidades de voz, capaz de leer, razonar y actuar sobre emails, calendarios, citas y recordatorios mediante interacción conversacional de voz multi-turn con RAG sobre datos históricos y documentos.

> **🎯 Proyecto Final - Curso Agentes IA 2ª Edición**: Este proyecto demuestra la implementación práctica de todos los conceptos técnicos avanzados del curso, incluyendo MCP (Model Context Protocol), sistemas multi-agente, Function Calling, RAG, y arquitecturas de agentes autónomos.

## 🎓 Conceptos del Curso Implementados

Este proyecto implementa y demuestra los siguientes conceptos técnicos del curso:

### Día 1: Model Context Protocol (MCP)
- ✅ **Protocolo MCP Estándar**: Implementación completa de JSON-RPC 2.0
- ✅ **Transportes Múltiples**: stdio, HTTP, HTTP+SSE
- ✅ **Servidores MCP**: Google Calendar, Gmail, Calendly, WhatsApp, Filesystem
- ✅ **Cliente MCP en Python**: Cliente genérico para cualquier servidor MCP
- ✅ **MCP Inspector**: Compatible con herramientas de depuración MCP

### Día 2: Function Calling y Agentes ReAct
- ✅ **Function Calling Nativo**: Integración con OpenAI/Anthropic/Nebius
- ✅ **Patrón ReAct (Reason + Act)**: Loop de razonamiento con herramientas
- ✅ **Tool Use**: Sistema de herramientas extensible y registrable
- ✅ **Prompt Templates**: Plantillas de prompts para diferentes contextos
- ✅ **Resources MCP**: Recursos dinámicos y estáticos

### Día 3: Sistemas Multi-Agente
- ✅ **Patrón Orquestador**: Agente coordinador que delega a especialistas
- ✅ **Agentes Especializados**: Calendar, Email, Scheduling, WhatsApp
- ✅ **Handoff entre Agentes**: Transferencia de tareas entre agentes
- ✅ **Paralelización**: Ejecución concurrente de herramientas cuando es posible
- ✅ **Estado Compartido**: Contexto compartido entre agentes

### Conceptos Avanzados Adicionales
- ✅ **RAG (Retrieval-Augmented Generation)**: Búsqueda semántica con pgvector
- ✅ **Voice Interface**: STT/TTS con interrupciones y fallbacks
- ✅ **Human-in-the-Loop**: Validación y confirmación de eventos
- ✅ **Persistencia de Estado**: Almacenamiento de conversaciones y contexto
- ✅ **Webhooks y Eventos**: Procesamiento asíncrono de eventos externos

---

## 🆕 Características Principales

| Característica | Estado | Descripción |
|----------------|--------|-------------|
| **Voz (STT/TTS)** | ✅ | Whisper (STT) + VibeVoice/Web Speech API (TTS) con fallback automático |
| **VAD (Voice Activity Detection)** | ✅ | Detección automática de voz, grabación continua, interrupciones |
| **RAG** | ✅ | Búsqueda semántica sobre emails, calendarios, notas y preferencias |
| **Multi-Agente** | ✅ | Arquitectura con agentes especializados (Calendar, Email, Scheduling, WhatsApp) |
| **Modo Desarrollador** | ✅ | Visualización en tiempo real de todo el proceso interno (RAG, LLM, Tools, etc.) |
| **Humanización de Respuestas** | ✅ | Limpieza automática de razonamiento técnico, extracción de nombres de eventos |
| **MCP Estándar** | ✅ | Protocolo MCP con JSON-RPC 2.0 y transportes stdio, HTTP, HTTP+SSE |
| **Google Calendar** | ✅ | Integración completa con OAuth 2.0 |
| **Gmail/IMAP** | ✅ | Lectura y búsqueda de emails vía IMAP |
| **Calendly** | ✅ | OAuth, listado de eventos, ingest y webhooks |
| **WhatsApp** | ✅ | Envío/recepción vía Twilio, almacenamiento de conversaciones, detección de eventos |
| **SMTP** | ✅ | Envío de emails |
| **Webhooks** | ✅ | Calendly webhooks con validación HMAC |
| **Validación de Mensajes** | ✅ | Filtrado automático de mensajes sin sentido o muy cortos |

---

## 🏗️ Arquitectura Técnica

### Visión General del Sistema

Este proyecto implementa una arquitectura completa de agente autónomo que demuestra todos los conceptos del curso:

1. **Frontend con VAD**: Detección de voz y grabación continua
2. **WebSocket Bidireccional**: Comunicación en tiempo real
3. **Orquestador Multi-Agente**: Coordinación de agentes especializados
4. **MCP Layer**: Protocolo estándar para herramientas
5. **RAG Pipeline**: Contexto histórico y semántico
6. **Humanización**: Post-procesamiento de respuestas

### Diagramas Visuales

#### Arquitectura de Componentes Principales

![Arquitectura de Componentes](docs/diagrams/arquitectura_componentes.svg)

Este diagrama muestra la arquitectura completa del sistema, desde el frontend hasta los servicios externos, pasando por el orquestador multi-agente y la capa MCP.

#### Flujo LangGraph (Sistema Multi-Agente)

![Flujo LangGraph](docs/diagrams/langgraph_flow.svg)

El grafo de LangGraph implementa el patrón orquestador con los siguientes nodos:
- **ENTRY**: Punto de entrada con `user_query`
- **INTENT**: Router que detecta la intención (Calendar, Email, Scheduling, Comms, General)
- **RAG**: Recuperación de contexto semántico
- **CONFLICT_CHECK**: Verificación de conflictos en agenda
- **POLICY**: Validación de políticas (horario laboral, etc.)
- **AGENT**: Agente especializado según intención
- **PLAN**: Planificación de herramientas a ejecutar
- **TOOL**: Ejecución de herramientas (MCP o local)
- **RESPONSE**: Generación de respuesta final
- **END**: Resultado final

#### Flujo Completo de Voz

![Flujo de Voz](docs/diagrams/flujo_voz_completo.svg)

Este diagrama detalla el flujo completo desde que el usuario habla hasta que recibe la respuesta por voz:
1. **VAD**: Detección automática de voz
2. **Conversión**: WebM → WAV (ffmpeg)
3. **STT**: Transcripción con Whisper (Groq)
4. **Validación**: Filtrado de mensajes sin sentido
5. **Procesamiento del Agente**: RAG → LLM → Tools → Humanización
6. **TTS**: VibeVoice (primario) o Web Speech API (fallback)
7. **Reproducción**: Streaming de audio con interrupciones
8. **Reactivación**: Micrófono se reactiva automáticamente

#### Sistema Multi-Agente con MCP

![Sistema Multi-Agente MCP](docs/diagrams/sistema_multiagente_mcp.svg)

Muestra cómo el orquestador coordina agentes especializados y cómo cada uno se comunica con servidores MCP:
- **Orchestrator Agent (ORCH)**: Coordinador principal
- **Agentes Especializados**: CAL, EMAIL, SCHED, WA
- **MCP Layer**: Protocolo estándar con múltiples transportes
- **Tool Registry**: Sistema centralizado de herramientas

> **📊 Nota**: Todos los diagramas SVG están disponibles en [`docs/diagrams/`](docs/diagrams/). Puedes visualizarlos directamente en el navegador o incluirlos en presentaciones.

### Componentes Principales

```
┌─────────────────────────────────────────────────────────────┐
│                    Voice Interface (WebSocket)              │
│              STT (Whisper) → Agent → TTS (VibeVoice)        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Multi-Agent Orchestrator (LangGraph)            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Supervisor│→ │ Calendar │  │  Email   │  │  Comms   │   │
│  │          │  │  Agent   │  │  Agent   │  │  Agent   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    MCP (Model Context Protocol)              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ stdio Client │  │  HTTP Client │  │  SSE Client  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    External Services                         │
│  Google Calendar │ Gmail/IMAP │ Calendly │ WhatsApp/Twilio  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    RAG (Supabase + pgvector)                │
│  Historical Emails │ Calendar Events │ Notes │ Preferences  │
└─────────────────────────────────────────────────────────────┘
```

### Flujo de Procesamiento Completo

#### 1. Captura y Transcripción de Voz (STT)
- **Voice Activity Detection (VAD)**: El frontend detecta automáticamente cuando el usuario habla
- **Grabación Continua**: Sistema de escucha continua que graba automáticamente cuando detecta voz
- **Conversión de Audio**: WebM → WAV usando `ffmpeg` (requerido)
- **Transcripción**: Whisper (Groq) convierte audio a texto
- **Validación Rápida**: Filtrado de mensajes sin sentido (muy cortos, solo palabras de relleno)
- **Feedback Inmediato**: El texto transcrito se muestra inmediatamente al usuario

#### 2. Procesamiento del Agente (Patrón ReAct + Multi-Agente)

**2.1. RAG Retrieval (Retrieval-Augmented Generation)**
- **Embeddings**: Generación de embeddings semánticos (Qwen3-Embedding-8B)
- **Búsqueda Vectorial**: Supabase pgvector para búsqueda por similitud
- **Contexto Histórico**: Emails, eventos, notas, preferencias almacenadas
- **Top-K Retrieval**: Configurable (default: 6 chunks más relevantes)

**2.2. Sistema Multi-Agente (Patrón Orquestador)**
- **Orchestrator Agent (ORCH)**: Coordinador principal que:
  - Analiza la intención del usuario
  - Decide qué agente especializado usar
  - Gestiona el flujo de iteraciones
  - Humaniza las respuestas finales

- **Agentes Especializados** (implementan patrón handoff):
  - **Calendar Agent (CAL)**: 
    - Tools: `list_agenda_events`, `create_calendar_event`, `confirm_agenda_event`
    - MCP: `google-calendar.list_events`, `google-calendar.create_event`
    - Contexto: Eventos del calendario, citas propuestas
  
  - **Email Agent (EMAIL)**:
    - Tools: `search_emails`, `read_email`, `send_email`
    - MCP: `imap.search_emails`, `imap.read_email`
    - Contexto: Historial de emails, preferencias de comunicación
  
  - **Scheduling Agent (SCHED)**:
    - Tools: `create_calendly_event`, `ingest_calendly_events`
    - MCP: `calendly.create_event`, `calendly.list_events`
    - Contexto: Eventos de Calendly, disponibilidad
  
  - **WhatsApp Agent (WA)**:
    - Tools: `send_whatsapp`
    - MCP: `whatsapp.send_message`
    - Contexto: Conversaciones almacenadas, eventos detectados

**2.3. Loop de Razonamiento (ReAct Pattern)**
- **Iteración 1**: 
  - LLM analiza la consulta con contexto RAG
  - Decide qué herramientas usar (Function Calling)
  - Muestra razonamiento interno (en modo desarrollador)
  
- **Iteración 2+**:
  - Procesa resultados de herramientas
  - Puede hacer llamadas adicionales si es necesario
  - Genera respuesta final con contexto completo

**2.4. Function Calling / Tool Use**
- **Tool Registry**: Sistema centralizado de herramientas
- **MCP Integration**: Prioriza herramientas MCP cuando están disponibles
- **Fallback Local**: Usa registro local si MCP falla
- **Tool Selection Logging**: Muestra todas las herramientas disponibles y la razón de selección

**2.5. Humanización de Respuestas**
- **Limpieza de Razonamiento**: Elimina tags `<think>` y razonamiento interno del LLM
- **Extracción de Nombres**: Usa nombres reales de eventos de tool results (no IDs)
- **Formato Natural**: Mejora listas, fechas, puntuación
- **Priorización de Tool Results**: Usa texto formateado de tools cuando está disponible

#### 3. Síntesis de Voz (TTS)
- **VibeVoice (Primario)**: TTS en tiempo real con streaming de audio
- **Fallback Automático**: Si VibeVoice falla o está ocupado:
  - **Web Speech API**: Síntesis de voz nativa del navegador (gratuita, sin latencia de red)
  - Activación automática cuando `chunks_sent === 0` o `fallback_available === true`
- **Interrupciones**: Si el usuario habla mientras el agente responde:
  - Detiene inmediatamente el audio (VibeVoice o Web Speech API)
  - Limpia la cola de audio
  - Cancela el procesamiento en curso
  - Reanuda la escucha para capturar la nueva consulta

#### 4. Modo Desarrollador
- **Toggle de Desarrollo**: Activa/desactiva visualización de logs internos
- **Logs en Tiempo Real**: Muestra todo el proceso como burbujas en la conversación:
  - **RAG**: Búsqueda de contexto, chunks encontrados, fuentes
  - **LLM**: Razonamiento interno, herramientas disponibles, decisiones
  - **TOOL**: Ejecución de herramientas, resultados, uso de MCP
  - **CLEAN**: Limpieza y humanización de respuestas
  - **AUDIO/STT**: Conversión de audio, transcripción
- **Identificación de Agentes**: Cada log muestra qué agente está procesando (CAL, EMAIL, ORCH, etc.)
- **Formato Visual**: Logs en gris con avatares distintivos para cada etapa

---

## 🚀 Inicio Rápido

### Prerrequisitos

- **Python 3.11+**
- **ffmpeg** (requerido para conversión de audio WebM → WAV)
  - Windows: `choco install ffmpeg` o descargar de [ffmpeg.org](https://ffmpeg.org/download.html)
  - Linux: `sudo apt-get install ffmpeg`
  - macOS: `brew install ffmpeg`
- **Supabase Account** (para RAG y base de datos)
- **Nebius API Key** (recomendado) o OpenAI/Anthropic
- **Google Cloud Account** (para Calendar/Gmail)
- **Calendly Account** (opcional)
- **Twilio Account** (opcional, para WhatsApp)
- **Groq API Key** (para STT con Whisper)

### Instalación

```bash
# Clonar repositorio
git clone <repository-url>
cd personal-coordination-voice-agent

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# o
.venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### Configuración

1. **Copiar archivo de entorno**:
```bash
cp .env.example .env
```

2. **Configurar variables de entorno** (ver `.env.example` para plantilla completa):

```env
# Core
ENVIRONMENT=development
LOG_LEVEL=INFO
LANGGRAPH_AGENT=true

# Supabase (RAG)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# LLM Provider (Nebius recomendado)
AI_PROVIDER=nebius
NEBIUS_API_KEY=your-nebius-key
NEBIUS_BASE_URL=https://tokenfactory.nebius.com
NEBIUS_MODEL_CHAT=Qwen3-235B-A22B-Thinking-2507
NEBIUS_MODEL_SPECIALIST=Qwen3-30B-A3B-Instruct-2507
NEBIUS_MODEL_ROUTER=gpt-oss-20b
NEBIUS_MODEL_EMBED=Qwen3-Embedding-8B

# Voz
VOICE_TTS_BACKEND=vibevoice
VIBEVOICE_BASE_URL=https://api.vibevoice.xyz
VOICE_STT_BACKEND=whisper
STT_PROVIDER=groq
GROQ_API_KEY=your-groq-key

# Google OAuth
GOOGLE_OAUTH_CLIENT_PATH=credentials/google_oauth_client.json
GOOGLE_OAUTH_TOKEN_PATH=credentials/google_oauth_token.json
GOOGLE_CALENDAR_EMAIL=your@gmail.com

# Calendly
CALENDLY_CLIENT_ID=your-client-id
CALENDLY_CLIENT_SECRET=your-client-secret
CALENDLY_REDIRECT_URI=http://localhost:8000/api/v1/calendly/callback

# SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASS=your-app-password

# IMAP
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your@gmail.com
IMAP_PASS=your-app-password
IMAP_USE_SSL=true

# MCP
USE_MOCK_MCP=false
MCP_CONFIG_PATH=app/mcp/mcp_servers.json
MCP_MAPPING_PATH=app/mcp/mapping.json
```

3. **Inicializar base de datos**:
   - Ejecutar `sql/init_supabase.sql` en Supabase SQL Editor
   - Esto crea las tablas necesarias y configura pgvector

4. **Configurar OAuth de Google**:
   - Crear proyecto en Google Cloud Console
   - Habilitar Calendar API y Gmail API
   - Crear credenciales OAuth 2.0
   - Guardar en `credentials/google_oauth_client.json`

5. **Iniciar servidor**:
```bash
uvicorn main:app --reload --port 8000
```

---

## 📡 API Endpoints

### Health & Info

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/healthz` | GET | Health check |
| `/api/v1/tools` | GET | Lista herramientas disponibles |
| `/api/v1/metrics` | GET | Métricas de ejecución |

### Agente Principal

**POST `/api/v1/text`**
- Procesa consultas de texto
- Soporta shortcuts directos: "agenda", "confirmados", etc.

```bash
curl -X POST "http://localhost:8000/api/v1/text" \
  -H "Content-Type: application/json" \
  -d '{"query": "¿Qué tengo en la agenda mañana?"}'
```

### Voz (WebSocket)

**WebSocket `/api/v1/voice`**
- Streaming bidireccional de audio
- Soporta modo texto y audio
- Sistema de interrupciones para cancelar procesamiento
- Logs estructurados en tiempo real

**Modo texto**:
```json
{"mode": "text", "text": "Hola, agenda con Juan mañana a las 10"}
```

**Modo audio**:
```json
{"mode": "audio", "audio_base64": "<wav_base64>"}
```

**Interrupción** (cuando el usuario habla mientras el agente responde):
```json
{"type": "interrupt", "message": "Usuario interrumpió"}
```

**Cancelación** (para mensajes sin sentido):
```json
{"type": "cancel", "reason": "message_no_sense", "text": "..."}
```

**Eventos de Log** (enviados por el servidor):
- `backend_ready`: Servidor listo
- `stt_completed`: Transcripción completada (texto mostrado inmediatamente)
- `agent_processing_started`: Agente inició procesamiento
- `agent_rag_started/completed`: Búsqueda RAG
- `agent_iteration_started`: Nueva iteración del agente
- `agent_tools_available`: Herramientas disponibles
- `agent_llm_reasoning`: Razonamiento interno del LLM
- `agent_tool_executing/completed`: Ejecución de herramientas
- `agent_response_ready`: Respuesta final humanizada lista
- `tts_started/completed/error`: Síntesis de voz
- `tts_first_chunk_sent`: Primer chunk de audio (latencia)

### Calendly

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/v1/calendly/auth_url` | GET | Obtener URL de autorización OAuth |
| `/api/v1/calendly/callback` | GET | Callback OAuth |
| `/api/v1/calendly/events` | GET | Listar eventos programados |
| `/api/v1/calendly/ingest` | POST | Ingestar eventos a Supabase |
| `/api/v1/calendly/webhook` | POST | Webhook para eventos en tiempo real |

### Email

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/v1/email/send` | POST | Enviar email vía SMTP |

### WhatsApp

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/v1/whatsapp/webhook` | POST | Webhook receptor de mensajes de Twilio |
| `/api/v1/whatsapp/process-conversations` | POST | Procesamiento batch de conversaciones |

**Flujo de WhatsApp**:
1. Twilio envía mensaje → Webhook recibe y valida firma
2. Mensaje almacenado en Supabase (`whatsapp_messages`, `whatsapp_conversations`)
3. Se recupera contexto de conversación (últimos N mensajes)
4. Agente procesa con contexto completo para detectar eventos
5. Respuesta enviada vía Twilio API
6. Procesamiento batch disponible para re-analizar conversaciones

---

## 🔌 MCP (Model Context Protocol) - Implementación Completa

Este proyecto implementa el protocolo MCP estándar (JSON-RPC 2.0) tal como se enseñó en el curso, demostrando todos los conceptos del Día 1 y Día 2.

### Transportes Soportados (Día 1)

1. **stdio**: Comunicación por entrada/salida estándar
   - Para integración con Cursor/Claude Desktop
   - Implementado en `app/mcp/clients/stdio_client.py`
   
2. **HTTP**: Comunicación HTTP POST (unidireccional)
   - Para servidores remotos
   - Implementado en `app/mcp/clients/http_client.py`
   - Soporta autenticación y headers personalizados
   
3. **HTTP+SSE**: HTTP POST + Server-Sent Events (bidireccional)
   - Para comunicación en tiempo real
   - Implementado en `app/mcp/clients/sse_client.py`
   - Soporta streaming de resultados

### Servidores MCP Configurados (Día 1 - Día 2)

Cada servidor MCP implementa el protocolo estándar con JSON-RPC 2.0:

- **`google-calendar`**: Integración con Google Calendar API
  - Tools: `list_events`, `create_event`, `update_event`
  - Transporte: HTTP (OAuth 2.0)
  
- **`imap`**: Cliente IMAP para lectura de emails
  - Tools: `search_emails`, `read_email`, `get_attachments`
  - Transporte: stdio (proceso local)
  
- **`calendly`**: Integración con Calendly API
  - Tools: `list_events`, `create_event`, `get_availability`
  - Transporte: HTTP (OAuth 2.0)
  
- **`whatsapp`**: Integración con Twilio WhatsApp API
  - Tools: `send_message`, `get_conversation_history`
  - Transporte: HTTP (REST API)
  
- **`filesystem`**: Acceso al sistema de archivos
  - Tools: `read_file`, `write_file`, `list_directory`
  - Transporte: stdio (proceso local)
  
- **`google-drive`**: Integración con Google Drive API
  - Tools: `list_files`, `download_file`, `upload_file`
  - Transporte: HTTP (OAuth 2.0)

### Prompt Templates y Resources (Día 2)

El sistema soporta:
- **Prompt Templates**: Plantillas reutilizables para diferentes contextos
- **Resources**: Recursos estáticos y dinámicos (archivos, datos, etc.)
- **Dynamic Resources**: Recursos que se generan en tiempo de ejecución

### Configuración MCP

Los servidores se configuran en `app/mcp/mcp_servers.json`:

```json
{
  "mcpServers": {
    "google-calendar": {
      "command": "python",
      "args": ["path/to/google_calendar_mcp_server.py"],
      "env": {
        "GOOGLE_OAUTH_CLIENT_PATH": "credentials/google_oauth_client.json"
      }
    }
  }
}
```

El mapeo de herramientas se define en `app/mcp/mapping.json`:

```json
{
  "list_cal_events": "google-calendar.list_events",
  "create_cal_event": "google-calendar.create_event",
  "search_emails": "imap.search_emails"
}
```

### Testing MCP (Día 1 - Día 2)

El proyecto incluye herramientas de testing para validar la implementación MCP:

```bash
# Probar cliente stdio
python scripts/test_mcp_protocol.py --mode stdio

# Probar cliente HTTP
python scripts/test_mcp_protocol.py --mode http

# Probar cliente SSE
python scripts/test_mcp_protocol.py --mode sse

# Probar todos los transportes
python scripts/test_mcp_protocol.py --mode all
```

**MCP Inspector**: Compatible con herramientas de depuración MCP estándar para inspeccionar servidores, tools, y resources.

> **📊 Diagramas**: Todos los diagramas SVG están disponibles en [`docs/diagrams/`](docs/diagrams/). Puedes visualizarlos directamente en el navegador o incluirlos en presentaciones.

---

## 🧪 Testing

```bash
# Ejecutar todos los tests
pytest

# Tests E2E
pytest tests/test_e2e.py

# Tests de deduplicación
pytest tests/test_deduplication.py
```

---

## 📁 Estructura del Proyecto

```
personal-coordination-voice-agent/
│
├── 📂 app/
│   ├── 📂 agents/              # Agentes y orquestación
│   │   ├── graph.py            # LangGraph multi-agente
│   │   ├── orchestrator.py    # Loop de razonamiento
│   │   ├── 📂 specialists/     # Agentes especializados
│   │   └── 📂 tools/           # Herramientas del agente
│   │
│   ├── 📂 api/                 # Endpoints FastAPI
│   │   ├── routes.py          # Rutas principales
│   │   ├── ws.py              # WebSocket voz
│   │   └── calendly.py        # Endpoints Calendly
│   │
│   ├── 📂 mcp/                 # Model Context Protocol
│   │   ├── 📂 protocol/        # JSON-RPC 2.0 y MCP
│   │   ├── 📂 clients/         # Clientes MCP (stdio, HTTP, SSE)
│   │   ├── 📂 servers/         # Servidores MCP de prueba
│   │   ├── mcp_servers.json   # Configuración servidores
│   │   └── mapping.json        # Mapeo tools → servidores
│   │
│   ├── 📂 services/            # Servicios core
│   │   ├── rag.py             # Pipeline RAG
│   │   ├── embedding.py       # Generación embeddings
│   │   └── metrics.py         # Métricas y observabilidad
│   │
│   ├── 📂 voice/               # Integración voz
│   │   ├── stt_whisper.py     # Speech-to-Text
│   │   └── vibevoice.py       # Text-to-Speech
│   │
│   └── main.py                # Aplicación FastAPI
│
├── 📂 Docs/                    # Documentación
│   ├── ESTADO_IMPLEMENTACION.md
│   ├── ESTADO_MCP_FINAL.md
│   ├── TEST_MCP_PROTOCOLO.md
│   ├── MEJORAS_VOZ.md
│   ├── IMAP_SETUP.md
│   └── WEBHOOKS.md
│
├── 📂 scripts/                 # Scripts utilitarios
│   ├── test_mcp_protocol.py   # Tests MCP
│   ├── ingest_gmail.py        # Ingest emails
│   └── extract_events_from_messages.py
│
├── 📂 tests/                   # Tests automatizados
│   ├── test_e2e.py            # Tests end-to-end
│   └── test_deduplication.py  # Tests deduplicación
│
├── 📂 sql/                     # Scripts SQL
│   └── init_supabase.sql      # Schema inicial
│
└── README.md                   # Este archivo
```

---

## 📚 Documentación Adicional

Toda la documentación detallada se encuentra en la carpeta [`Docs/`](Docs/README.md):

- **[ESTADO_IMPLEMENTACION.md](Docs/ESTADO_IMPLEMENTACION.md)**: Estado general del proyecto y funcionalidades implementadas
- **[ESTADO_MCP_FINAL.md](Docs/ESTADO_MCP_FINAL.md)**: Estado de la implementación MCP estándar (JSON-RPC 2.0, transportes)
- **[TEST_MCP_PROTOCOLO.md](Docs/TEST_MCP_PROTOCOLO.md)**: Guía completa para probar los transportes MCP
- **[MEJORAS_VOZ.md](Docs/MEJORAS_VOZ.md)**: Mejoras en integración de voz (STT/TTS streaming)
- **[IMAP_SETUP.md](Docs/IMAP_SETUP.md)**: Configuración y uso de IMAP para lectura de emails
- **[WEBHOOKS.md](Docs/WEBHOOKS.md)**: Configuración y testing de webhooks (Calendly)
- **[WHATSAPP_WEBHOOK.md](Docs/WHATSAPP_WEBHOOK.md)**: Configuración de webhook de WhatsApp con Twilio
- **[WHATSAPP_CONVERSACIONES.md](Docs/WHATSAPP_CONVERSACIONES.md)**: Sistema de almacenamiento y procesamiento de conversaciones
- **[TWILIO_SETUP_PASO_A_PASO.md](Docs/TWILIO_SETUP_PASO_A_PASO.md)**: Guía paso a paso para configurar Twilio
- **[INSTALACION_FFMPEG.md](Docs/INSTALACION_FFMPEG.md)**: Instrucciones para instalar ffmpeg (requerido para conversión de audio)
- **[PENDIENTES_IMPLEMENTACION.md](Docs/PENDIENTES_IMPLEMENTACION.md)**: Lista de tareas pendientes y mejoras futuras

---

## 🔧 Desarrollo Técnico

### Arquitectura Multi-Agente (Día 3)

El proyecto implementa el **Patrón Orquestador** tal como se enseñó en el curso:

```python
# app/agents/orchestrator.py
class AgentService:
    async def process_query(self, query, ...):
        # 1. RAG Retrieval
        rag_context = await self._retrieve_rag_context(query)
        
        # 2. Loop de iteraciones (ReAct)
        for iteration in range(max_iterations):
            # 3. LLM Reasoning con Function Calling
            response = await self._call_llm(messages, tools)
            
            # 4. Tool Execution (vía MCP o registro local)
            if tool_calls:
                results = await execute_tools(tool_calls)
                messages.append(tool_results)
            else:
                # 5. Respuesta final
                return self._humanize_response(response)
```

**Características del Patrón Orquestador**:
- ✅ **Delegación Inteligente**: El orquestador decide qué agente usar
- ✅ **Contexto Compartido**: Todos los agentes acceden al mismo contexto RAG
- ✅ **Handoff Automático**: Si un agente no puede resolver, se delega a otro
- ✅ **Paralelización**: Herramientas independientes se ejecutan en paralelo

### Function Calling / Tool Use (Día 2)

Implementación completa de Function Calling nativo:

```python
# El LLM recibe definiciones de herramientas
tools = [
    {
        "type": "function",
        "function": {
            "name": "list_agenda_events",
            "description": "Lista eventos de la agenda",
            "parameters": {...}
        }
    }
]

# El LLM decide qué herramientas usar
response = await llm.chat.completions.create(
    messages=messages,
    tools=tools,
    tool_choice="auto"  # El LLM decide
)

# Ejecutamos las herramientas solicitadas
for tool_call in response.tool_calls:
    result = await execute_tool(tool_call)
```

**Características**:
- ✅ **Tool Registry Centralizado**: Todas las herramientas en un solo lugar
- ✅ **MCP Integration**: Prioriza herramientas MCP cuando están disponibles
- ✅ **Fallback Local**: Usa registro local si MCP falla
- ✅ **Logging Detallado**: Muestra razonamiento del LLM para elegir herramientas

### Modo Desarrollador (Observabilidad)

El modo desarrollador muestra en tiempo real todo el proceso interno del agente, demostrando el flujo completo:

1. **Activar**: Toggle "Modo Desarrollador" en el frontend
2. **Visualización**: Los logs aparecen como burbujas en la conversación:
   - **RAG**: Búsqueda de contexto, chunks encontrados, fuentes
   - **LLM**: Razonamiento interno, herramientas disponibles, decisiones
   - **TOOL**: Ejecución de herramientas, resultados MCP, protocolo usado
   - **CLEAN**: Limpieza y humanización de respuestas
   - **AUDIO/STT**: Conversión y transcripción
3. **Agentes**: Cada log muestra el agente responsable (CAL, EMAIL, ORCH, etc.)
4. **MCP Details**: Muestra qué herramientas usan MCP y cuáles son locales

### Añadir Nueva Herramienta (Día 2)

Siguiendo el patrón del curso:

1. **Crear tool** en `app/agents/tools/my_tool.py`:
```python
class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    async def execute(self, param1: str, **kwargs) -> Dict[str, Any]:
        # Lógica del tool
        return self._success_response({"result": "..."})
```

2. **Registrar** en `app/agents/tools/registry.py`:
```python
tool_registry.register_tool(MyTool())
```

3. **Añadir schema** en `app/schemas/tool_schemas.py` para Function Calling

4. **(Opcional) Crear servidor MCP** (Día 1):
   - Implementar JSON-RPC 2.0
   - Configurar en `app/mcp/mcp_servers.json`
   - Mapear en `app/mcp/mapping.json`

5. El tool aparecerá automáticamente en `agent_tools_available` logs

### Añadir Nuevo Agente Especializado (Día 3)

Implementando el patrón orquestador:

1. **Crear agente** en `app/agents/specialists/my_agent.py`:
```python
class MyAgent:
    def __init__(self):
        self.tools = ["tool1", "tool2"]
        self.context = "Descripción del agente"
```

2. **Integrar en orquestador** en `app/agents/orchestrator.py`:
   - Añadir detección de intención
   - Asignar tools específicos del agente
   - Configurar contexto especializado

3. El agente se identificará automáticamente en los logs con su código (ej: "MYAG")

### Humanización de Respuestas (Post-Procesamiento)

El sistema humaniza automáticamente las respuestas del LLM para hacerlas más naturales:

1. **Limpieza de Razonamiento**: 
   - Elimina tags `<think>` y `<think>`
   - Remueve frases de razonamiento interno ("We note that", "Let's process", etc.)
   - Extrae solo la respuesta final al usuario

2. **Extracción de Nombres**: 
   - Usa nombres reales de eventos de tool results en lugar de IDs genéricos
   - Mapea `event_id=15` → `"Entrevista Jhon Hernandez"`
   - Mejora la legibilidad de las respuestas

3. **Formato Natural**: 
   - Mejora listas y viñetas
   - Formatea fechas en español natural
   - Normaliza espacios y saltos de línea
   - Asegura puntuación correcta

4. **Uso de Tool Results**: 
   - Prioriza texto formateado de tools cuando está disponible
   - Evita mostrar razonamiento técnico del LLM
   - Presenta información estructurada de manera natural

### Fallback de TTS (Resiliencia)

El sistema implementa un patrón de fallback robusto:

1. **VibeVoice (Primario)**: 
   - TTS en tiempo real con streaming WebSocket
   - Latencia baja para conversaciones naturales
   - Soporte para múltiples voces y idiomas

2. **Web Speech API (Fallback)**: 
   - Activación automática si:
     - VibeVoice está ocupado (`backend_busy`)
     - No se reciben chunks (`chunks_sent === 0`)
     - Error en VibeVoice o timeout
   - **Ventajas**: Sin latencia de red, gratuito, siempre disponible
   - **Implementación**: Browser-native, no requiere servidor

3. **Interrupciones (Voice Activity Detection)**:
   - El usuario puede interrumpir hablando
   - Detección automática de voz durante TTS
   - Detiene inmediatamente audio (VibeVoice o Web Speech API)
   - Limpia cola de audio y reanuda escucha

---

## 🚢 Despliegue

### Docker

```bash
docker build -t personal-coordination-agent .
docker run -p 8000:8000 --env-file .env personal-coordination-agent
```

### Cloud Run / Railway / Render

Ver `Docs/DEPLOYMENT.md` (si existe) para guías específicas.

---

## 📄 Licencia

MIT License

---

## 🙋‍♂️ Soporte

- **API Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/healthz`
- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)

---

## 🎯 Objetivos de Aprendizaje Cumplidos

Este proyecto demuestra la aplicación práctica de todos los conceptos del curso:

✅ **MCP (Día 1)**: Protocolo estándar, transportes múltiples, servidores y clientes  
✅ **Function Calling (Día 2)**: Tool use nativo, ReAct pattern, prompt templates  
✅ **Multi-Agente (Día 3)**: Patrón orquestador, handoff, paralelización  
✅ **RAG**: Búsqueda semántica y contexto histórico  
✅ **Voice Interface**: STT/TTS con interrupciones y fallbacks  
✅ **Observabilidad**: Modo desarrollador con logs en tiempo real  
✅ **Integraciones**: Calendar, Email, WhatsApp, Calendly vía MCP  
✅ **Human-in-the-Loop**: Validación y confirmación de acciones  

---

Built with ❤️ for personal productivity automation | **Proyecto Final - Curso Agentes IA 2ª Edición**

# 🚀 Roadmap Priorizado - Proyecto Final (ADAPTADO A EVENT MANAGER)

**Objetivo**: Adaptar técnicas del proyecto final del curso a nuestro Event Manager  
**Proyecto Real**: Personal Coordination Voice Agent (Event Manager)  
**Técnicas del Curso**: MCP, Web Scraping, Human-in-the-Loop, Multi-Agente  
**Base de datos**: Supabase (ya implementado)  
**Tracing/Evaluación**: LangSmith + Langfuse  
**Frontend**: Web simple para probar y visualizar

---

## 🎯 ADAPTACIÓN: De "Curación de Contenidos" a "Event Discovery"

**El proyecto del curso es un MOLDE** - debemos adaptarlo a nuestro caso de uso:

| Proyecto Curso (Molde) | Event Manager (Nuestro) |
|------------------------|--------------------------|
| Monitorizar Telegram/WhatsApp | Monitorizar Gmail + Web scraping sitios eventos |
| Extraer URLs genéricas | Extraer URLs de eventos + fechas/lugares |
| Procesar contenido web | Procesar páginas de eventos |
| Publicar posts en web | Sugerir eventos → Aprobar → Google Calendar |
| Tabla `posts` | Tabla `events_suggested` (o usar `extracted_events`) |

---

## 📋 Prioridades (Orden de Implementación)

### **Estado Actual del Proyecto** 📊

| Tarea | Estado | Archivos Creados/Modificados |
|-------|--------|------------------------------|
| 1.1 Tabla posts en Supabase | ✅ COMPLETADO | `sql/add_posts_tables.sql` (ejecutado) |
| 1.2 URL Extraction Tool | ✅ COMPLETADO | `app/agents/tools/url_extraction_tool.py`, `app/agents/tools/registry.py`, `app/schemas/tool_schemas.py` |
| 1.3 Web Scraping Tool | ✅ COMPLETADO | `app/agents/tools/web_scraping_tool.py`, `app/agents/tools/registry.py`, `app/schemas/tool_schemas.py` |
| 1.4 EventAgent (adaptado) | ✅ COMPLETADO | `app/agents/specialists/event_agent.py`, `app/agents/specialists/__init__.py` |
| 1.5 API Endpoints (events.py) | ✅ COMPLETADO | `app/api/events.py`, `app/config/database.py` (métodos añadidos), `app/main.py` |
| 1.6 Frontend (events.html) | ✅ COMPLETADO | `static/events.html` |

---

### **FASE 1: MVP Funcional Rápido** (3-4 días) ⚡

**Objetivo**: Tener algo funcionando end-to-end lo antes posible

#### 1.1 Tabla de Posts en Supabase (30 min) ✅
```sql
-- Ejecutar en Supabase SQL Editor
-- Archivo: sql/add_posts_tables.sql (NUEVO - compatible con esquema existente)
-- Añade sin modificar tablas existentes:
-- - Tabla posts (con status: pending/approved/rejected/published)
-- - Tabla curation_state (para persistencia de estado)
-- - Vistas: posts_pending, posts_published
-- - RLS policies configuradas
-- - Idempotente (puede ejecutarse múltiples veces)
```

#### 1.2 URL Extraction Tool (1 hora) ✅ COMPLETADO
```python
# app/agents/tools/url_extraction_tool.py ✅ CREADO
# - Extrae URLs usando regex
# - Valida URLs (http/https)
# - Normaliza URLs (elimina tracking params)
# - Elimina duplicados
# - Registrado en tool_registry
# - Añadido a TOOL_DEFINITIONS
# Basado en: https://github.com/juananpe/google-image-search-mcp-python
```

#### 1.3 Web Scraping Básico (2 horas) ✅ COMPLETADO
```python
# app/agents/tools/web_scraping_tool.py ✅ CREADO
# - Usa httpx + BeautifulSoup
# - Extrae título (Open Graph, Twitter Card, <title>, h1)
# - Extrae descripción (Open Graph, Twitter Card, meta description)
# - Extrae imagen destacada (Open Graph, Twitter Card, primera imagen grande)
# - Opcional: extrae texto del contenido
# - Headers de navegador real para evitar bloqueos
# - Timeout de 30s y manejo de errores
# - Registrado en tool_registry y TOOL_DEFINITIONS
# Referencia: https://youtu.be/J_T99KC1roI (Playwright MCP para futuro)
```

#### 1.4 EventAgent Básico (2 horas) 🆕 ADAPTADO
```python
# app/agents/specialists/event_agent.py
# ADAPTADO: En lugar de ContentAgent genérico, EventAgent especializado
# - Usa web_scraping_tool para obtener contenido de URLs de eventos
# - Extrae: título, fecha, hora, lugar, descripción
# - Genera resumen del evento con LLM (2-3 líneas)
# - Determina relevancia usando RAG + preferencias del usuario
# - Retorna estructura de evento sugerido
# - Puede usar extracted_events existente o crear events_suggested
```

#### 1.5 API Endpoints para Eventos (1 hora) 🆕 ADAPTADO
```python
# app/api/events.py (en lugar de posts.py)
# POST /api/v1/events/suggest - Sugerir evento (crea en extracted_events o events_suggested)
# GET /api/v1/events/suggested - Listar eventos sugeridos (status: suggested)
# POST /api/v1/events/{id}/approve - Aprobar → Crear en Google Calendar
# POST /api/v1/events/{id}/reject - Rechazar (status: rejected)
# GET /api/v1/events - Listar todos los eventos (sugeridos, aprobados, rechazados)
```

#### 1.6 Frontend Básico para Eventos (2 horas) 🆕 ADAPTADO
```html
# static/events.html
# - Listar eventos sugeridos (con relevancia score)
# - Vista de aprobación con detalles: título, fecha, lugar, descripción
# - Botones: Aprobar (→ Google Calendar) | Rechazar | Modificar
# - Mostrar imagen del evento si existe
# - Mostrar source_url del evento
```

**Resultado**: Sistema funcional básico para probar el flujo completo

---

### **📝 Notas Técnicas de Implementación**

#### **URL Extraction Tool - Detalles Técnicos** ✅

**Archivos modificados**:
- ✅ `app/agents/tools/url_extraction_tool.py` - Tool implementado
- ✅ `app/agents/tools/registry.py` - Registrado en `_register_default_tools()`
- ✅ `app/agents/tools/__init__.py` - Exportado en `__all__`
- ✅ `app/schemas/tool_schemas.py` - Añadido a `TOOL_DEFINITIONS` y `ToolName` enum

**Características implementadas**:
- ✅ Extracción de URLs con regex (http/https)
- ✅ Validación de URLs (scheme + netloc)
- ✅ Normalización de URLs (elimina parámetros de tracking como utm_*)
- ✅ Eliminación de duplicados
- ✅ Respuestas estandarizadas (success/error)
- ✅ Logging completo

**Uso**:
```python
from app.agents.tools import tool_registry

result = await tool_registry.execute_tool(
    "extract_urls",
    text="Mira este artículo: https://example.com/article?utm_source=twitter",
    normalize=True,
    remove_duplicates=True
)
# Result: {"success": True, "urls": ["https://example.com/article"], "count": 1}
```

**✅ MVP Event Discovery COMPLETADO** - Todas las tareas principales están implementadas

---

### **FASE 2: Integración MCP y Mensajería** (2-3 días) 📱

#### 2.1 Event Extraction de Emails (2 horas) 🆕 ADAPTADO
```python
# Usar IMAP existente (app/agents/tools/imap_search_tool.py)
# Filtrar emails con información de eventos
# Tool: extract_events_from_emails(limit, since)
# - Buscar emails con palabras clave: "evento", "conferencia", "meeting", etc.
# - Extraer URLs de eventos de emails
# - Extraer fechas/lugares del texto
# - Ya tenemos: imap_search_tool, imap_read_tool
```

#### 2.2 News Scraping Tool (3-4 horas) ✅ COMPLETADO
```python
# app/agents/tools/news_scraping_tool.py ✅ CREADO
# - Scrapea sitios de noticias configurables (TechCrunch, HackerNews, The Verge)
# - Busca menciones de eventos usando keywords (conferencia, event, meetup, etc.)
# - Extrae información de eventos de las noticias
# - Retorna lista de eventos encontrados con información extraída
# - Usa web_scraping_tool internamente
# - Registrado en tool_registry
# Caso de uso: "Conferencia NeurIPS 2025 anunciada" → Sugerir evento
```

#### 2.3 Event Site Scraping (2 horas) 🆕 ADAPTADO
```python
# Scrapear sitios específicos de eventos (configurables)
# - Eventbrite, Meetup, sitios de conferencias
# - Tool: scrape_event_sites(sites, categories)
# - Filtrar eventos relevantes usando RAG
# - Crear eventos sugeridos
# Referencia: https://youtu.be/J_T99KC1roI (Playwright MCP para futuro)
# Por ahora: usar web_scraping_tool existente
```

**Resultado**: Monitorización automática de mensajes

---

### **FASE 3: LangSmith + Langfuse Integration** (1-2 días) 📊

#### 3.1 LangSmith Setup (2 horas)
```python
# app/services/tracing.py
# Integrar LangSmith para tracing de LangGraph
# Referencia: https://docs.smith.langchain.com/
# Ejemplo: https://github.com/openai/openai-agents-python
```

**Configuración**:
```python
# .env
LANGCHAIN_API_KEY=your_key
LANGCHAIN_PROJECT=personal-coordination-agent
LANGCHAIN_TRACING_V2=true
```

#### 3.2 Langfuse Setup (2 horas)
```python
# app/services/evaluation.py
# Integrar Langfuse para evaluación
# Usar con OpenAI Agents SDK
# Referencia: Dia 3/LangFuse/integration_openai_agents.ipynb
```

**Configuración**:
```python
# .env
LANGFUSE_PUBLIC_KEY=your_key
LANGFUSE_SECRET_KEY=your_secret
LANGFUSE_HOST=https://cloud.langfuse.com
```

#### 3.3 Evaluadores (2 horas)
```python
# app/evaluators/
# - Evaluador de calidad de resúmenes (LLM como juez)
# - Evaluador de extracción de URLs
# - Evaluador de generación de imágenes
```

**Resultado**: Observabilidad completa y evaluación automática

---

### **FASE 4: Human-in-the-Loop Mejorado** (1 día) 👤

#### 4.1 Interfaz de Aprobación Mejorada (3 horas)
```html
# static/approve.html
# - Vista previa de posts con imagen
# - Edición inline de título/resumen
# - Regenerar imagen
# - Historial de decisiones
```

#### 4.2 Modificación de Posts (2 horas)
```python
# POST /api/v1/posts/{id}/modify
# - Regenerar resumen
# - Regenerar imagen
# - Editar título
```

**Resultado**: Interfaz completa para aprobación humana

---

### **FASE 5: Scheduling y Automatización** (1 día) ⏰

#### 5.1 Scheduler con APScheduler (2 horas)
```python
# app/scheduler/content_curation_job.py
# Ejecutar diariamente a las 9 AM
# - Leer mensajes nuevos
# - Extraer URLs
# - Procesar y crear posts pendientes
```

#### 5.2 Persistencia de Estado (1 hora)
```python
# Tabla en Supabase: curation_state
# - last_processed_message_id
# - last_execution_time
# - error_log
```

**Resultado**: Ejecución automática diaria

---

## 🛠️ Estructura de Archivos Propuesta

```
Proyecto/personal-coordination-voice-agent/
├── app/
│   ├── agents/
│   │   ├── specialists/
│   │   │   └── content_agent.py          # NUEVO: Procesamiento de URLs
│   │   └── tools/
│   │       ├── url_extraction_tool.py    # NUEVO: Extraer URLs
│   │       ├── web_scraping_tool.py      # NUEVO: Scraping básico
│   │       └── image_generation_tool.py  # NUEVO: Generar imágenes
│   ├── api/
│   │   └── posts.py                      # NUEVO: Endpoints de posts
│   ├── mcp/
│   │   └── servers/
│   │       └── telegram_mcp.py          # NUEVO: Telegram MCP
│   ├── services/
│   │   ├── tracing.py                    # NUEVO: LangSmith
│   │   └── evaluation.py                 # NUEVO: Langfuse
│   ├── scheduler/
│   │   └── content_curation_job.py      # NUEVO: Job diario
│   └── evaluators/
│       ├── summary_evaluator.py         # NUEVO: Evaluar resúmenes
│       └── url_extraction_evaluator.py  # NUEVO: Evaluar extracción
├── static/
│   ├── posts.html                        # NUEVO: Visualizar posts
│   └── approve.html                      # NUEVO: Aprobar posts
└── scripts/
    └── setup_supabase_posts.sql          # NUEVO: Setup DB
```

---

## 📚 Recursos del Curso a Usar

### **Repositorios y Ejemplos**:
1. **Google Image Search MCP**: https://github.com/juananpe/google-image-search-mcp-python
   - Ejemplo de servidor MCP en Python
   - Estructura para Telegram MCP

2. **Research Server MCP**: https://gist.github.com/juananpe/a9f13d7d17eb7202e1f3cc3ce4ef400e
   - Ejemplo de servidor MCP completo
   - Patrón a seguir

3. **Cliente MCP en Python**: https://gist.github.com/juananpe/588b0967cd6f1ed3385e56f81ed87896
   - Cliente MCP general
   - Ya tenemos implementado, pero podemos mejorar

4. **OpenAI Agents SDK**: https://github.com/openai/openai-agents-python
   - Ejemplos de multi-agente
   - Integración con MCP

### **Vídeos Tutoriales**:
- **Playwright MCP**: https://youtu.be/J_T99KC1roI
- **Implementando MCP**: https://youtu.be/UEZABGkibh0
- **MCP Avanzado**: https://youtu.be/z08J43j94WQ

### **Documentación**:
- **OpenAI Function Calling**: https://platform.openai.com/docs/guides/function-calling
- **Anthropic Tool Use**: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
- **LangSmith**: https://docs.smith.langchain.com/
- **Langfuse**: https://langfuse.com/docs

---

## 🎯 Plan de Implementación Rápida (MVP en 3-4 días)

### **Día 1: Fundamentos**
- ✅ Crear tabla `posts` en Supabase
- ✅ URL Extraction Tool
- ✅ Web Scraping Tool básico (requests + BeautifulSoup)
- ✅ API endpoints básicos

### **Día 2: Procesamiento**
- ✅ ContentAgent básico
- ✅ Generación de resúmenes
- ✅ Extracción de imágenes
- ✅ Frontend básico para visualizar

### **Día 3: Integración**
- ✅ Telegram/WhatsApp reading
- ✅ Flujo completo: mensaje → URL → post → aprobación
- ✅ Testing end-to-end

### **Día 4: Pulido**
- ✅ LangSmith/Langfuse integration
- ✅ Interfaz de aprobación mejorada
- ✅ Documentación

---

## 🔧 Configuración Inicial

### **1. Variables de Entorno (.env)**
```bash
# Ya existentes
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...

# Nuevas para el proyecto
# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# LangSmith
LANGCHAIN_API_KEY=...
LANGCHAIN_PROJECT=personal-coordination-agent
LANGCHAIN_TRACING_V2=true

# Langfuse
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com

# OpenAI (para generación de imágenes)
OPENAI_API_KEY=...
```

### **2. Dependencias (requirements.txt)**
```txt
# Añadir estas dependencias
beautifulsoup4>=4.12.0
python-telegram-bot>=20.0
langsmith>=0.1.0
langfuse>=2.0.0
playwright>=1.40.0  # Para MCP Playwright
```

---

## 🚀 Quick Start: Implementar MVP

### **Paso 1: Setup Supabase (5 min)**
```sql
-- Ejecutar en Supabase SQL Editor
-- (Ver SQL arriba en Fase 1.1)
```

### **Paso 2: URL Extraction Tool (30 min)**
```python
# Crear app/agents/tools/url_extraction_tool.py
# Implementar extracción con regex
```

### **Paso 3: Web Scraping Tool (1 hora)**
```python
# Crear app/agents/tools/web_scraping_tool.py
# Usar requests + BeautifulSoup
```

### **Paso 4: ContentAgent (1 hora)**
```python
# Crear app/agents/specialists/content_agent.py
# Integrar con LLM para resúmenes
```

### **Paso 5: API Endpoints (30 min)**
```python
# Crear app/api/posts.py
# Endpoints básicos CRUD
```

### **Paso 6: Frontend (1 hora)**
```html
# Crear static/posts.html
# Visualización básica
```

**Total**: ~4 horas para MVP funcional

---

## 📊 Integración LangSmith + Langfuse

### **LangSmith (Tracing)**
```python
# app/services/tracing.py
from langsmith import traceable
from langchain_core.tracers import LangChainTracer

# Configurar en settings.py
langsmith_api_key: str = Field(default="", env="LANGCHAIN_API_KEY")
langsmith_project: str = Field(default="personal-coordination-agent", env="LANGCHAIN_PROJECT")

# Usar en agent_orchestrator
@traceable(name="content_curation")
async def process_url(url: str):
    # Tu código aquí
    pass
```

### **Langfuse (Evaluación)**
```python
# app/services/evaluation.py
from langfuse import Langfuse
from langfuse.decorators import langfuse_context, observe

# Configurar
langfuse = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host
)

# Decorar funciones
@observe(name="generate_summary")
async def generate_summary(content: str):
    # Tu código aquí
    pass
```

### **Evaluadores**
```python
# app/evaluators/summary_evaluator.py
# Usar LLM como juez para evaluar calidad de resúmenes
# Comparar resumen generado vs contenido original
```

---

## 🎨 Frontend Web Simple

### **posts.html** (Visualización)
```html
<!DOCTYPE html>
<html>
<head>
    <title>Posts Publicados</title>
    <style>
        /* CSS moderno tipo cards */
        .post-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 16px;
            margin: 16px 0;
        }
    </style>
</head>
<body>
    <h1>Posts Publicados</h1>
    <div id="posts-container"></div>
    
    <script>
        // Fetch desde Supabase o API
        async function loadPosts() {
            const response = await fetch('/api/v1/posts?status=published');
            const posts = await response.json();
            // Renderizar cards
        }
        loadPosts();
    </script>
</body>
</html>
```

### **approve.html** (Aprobación)
```html
<!DOCTYPE html>
<html>
<head>
    <title>Aprobar Posts</title>
</head>
<body>
    <h1>Posts Pendientes de Aprobación</h1>
    <div id="pending-posts"></div>
    
    <script>
        // Cargar posts pendientes
        // Botones aprobar/rechazar/modificar
    </script>
</body>
</html>
```

---

## ✅ Checklist de Implementación

### **Fase 1: MVP** (3-4 días)
- [ ] Tabla `posts` en Supabase
- [ ] URL Extraction Tool
- [ ] Web Scraping Tool
- [ ] ContentAgent básico
- [ ] API endpoints
- [ ] Frontend básico

### **Fase 2: MCP** (2-3 días)
- [ ] WhatsApp reading
- [ ] Telegram MCP server
- [ ] Playwright MCP integration

### **Fase 3: Observabilidad** (1-2 días)
- [ ] LangSmith setup
- [ ] Langfuse setup
- [ ] Evaluadores básicos

### **Fase 4: Human-in-the-Loop** (1 día)
- [ ] Interfaz de aprobación mejorada
- [ ] Modificación de posts

### **Fase 5: Automatización** (1 día)
- [ ] Scheduler
- [ ] Persistencia de estado

---

## 🎯 Próximos Pasos Inmediatos

1. **Crear tabla en Supabase** (5 min)
2. **Implementar URL Extraction Tool** (30 min)
3. **Implementar Web Scraping básico** (1 hora)
4. **Crear ContentAgent** (1 hora)
5. **Añadir endpoints API** (30 min)
6. **Frontend básico** (1 hora)

**Total**: ~4 horas para tener algo funcional

---

## 📝 Notas Importantes

1. **Supabase en lugar de Flask+SQLite**: Ya tenemos Supabase, usémoslo directamente
2. **LangSmith + Langfuse**: Ambos son útiles, LangSmith para tracing, Langfuse para evaluación
3. **Playwright MCP**: Usar cuando sea necesario para contenido dinámico, pero empezar con requests+BeautifulSoup
4. **Telegram MCP**: Basarse en ejemplos del curso (google-image-search-mcp-python)
5. **Frontend simple**: Empezar con HTML/JS vanilla, luego mejorar si es necesario

---

**¿Empezamos con la Fase 1 (MVP)?** 🚀


# 🎯 Roadmap Adaptado - Event Discovery para Event Manager

**Proyecto**: Personal Coordination Voice Agent (Event Manager)  
**Adaptación**: Técnicas del proyecto final del curso aplicadas a gestión de eventos  
**Fecha**: Diciembre 2025

---

## 💡 Visión: Event Discovery Inteligente

En lugar de monitorizar Telegram/WhatsApp para URLs genéricas, usamos las mismas técnicas para:
1. **Descubrir eventos** desde múltiples fuentes (emails, noticias, sitios web)
2. **Procesar y evaluar** relevancia de eventos
3. **Sugerir eventos** al usuario con Human-in-the-Loop
4. **Crear en Google Calendar** cuando el usuario aprueba

---

## 🚀 Flujo Adaptado

```
┌─────────────────────────────────────────────────────────┐
│  FUENTES DE EVENTOS (Equivalente a Telegram/WhatsApp)  │
│  1. Gmail: Emails con información de eventos            │
│  2. Noticias: Scrapear noticias relevantes              │
│  3. Sitios Web: Eventbrite, Meetup, conferencias       │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  EXTRACCIÓN (Equivalente a extraer URLs)                 │
│  - Extraer URLs de eventos de emails                    │
│  - Extraer fechas, lugares, descripciones               │
│  - Identificar eventos en noticias                       │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  PROCESAMIENTO (Equivalente a procesar URLs)            │
│  - Scrapear páginas de eventos (web_scraping_tool)      │
│  - Extraer: título, fecha, lugar, descripción           │
│  - Generar resumen del evento (LLM)                     │
│  - Determinar relevancia (RAG + preferencias)          │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  HUMAN-IN-THE-LOOP (Aprobación)                          │
│  - Mostrar eventos sugeridos con relevancia              │
│  - Usuario aprueba/rechaza/modifica                     │
│  - Si aprueba → Crear en Google Calendar                │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  ALMACENAMIENTO (Equivalente a publicar)                 │
│  - Guardar en extracted_events (status: suggested)      │
│  - Si aprobado → status: approved → Google Calendar     │
│  - Frontend para ver eventos sugeridos                  │
└─────────────────────────────────────────────────────────┘
```

---

## 📋 Plan de Implementación Adaptado

### **FASE 1: Event Discovery MVP** (3-4 días) ⚡

#### 1.1 Tabla events_suggested (o usar extracted_events) ✅
```sql
-- OPCIÓN A: Usar extracted_events existente
-- Añadir columna: relevance_score FLOAT
-- Usar status: 'suggested' | 'approved' | 'rejected' | 'created'

-- OPCIÓN B: Crear tabla nueva events_suggested
-- Similar a posts pero para eventos
-- Ya tenemos extracted_events, podemos extender
```

#### 1.2 Event Extraction Tool 🆕
```python
# app/agents/tools/event_extraction_tool.py
# - Extraer URLs de eventos de emails (usar url_extraction_tool)
# - Extraer fechas/lugares de texto usando regex + NLP básico
# - Usar IMAP existente para leer emails
# - Filtrar emails con palabras clave de eventos
```

#### 1.3 News Scraping Tool 🆕 ⭐ NUEVA IDEA
```python
# app/agents/tools/news_scraping_tool.py
# - Scrapear sitios de noticias configurables
# - Buscar menciones de eventos/conferencias
# - Extraer información del evento
# - Determinar relevancia usando RAG
# - Caso de uso: "OpenAI anuncia conferencia GPT-5" → Sugerir evento
```

#### 1.4 EventAgent 🆕 (Adaptado de ContentAgent)
```python
# app/agents/specialists/event_agent.py
# - Procesa URLs de eventos usando web_scraping_tool
# - Extrae: título, fecha, hora, lugar, descripción
# - Genera resumen del evento con LLM (2-3 líneas)
# - Determina relevancia usando RAG + preferencias
# - Retorna evento sugerido (estructura compatible con extracted_events)
```

#### 1.5 API Endpoints para Eventos 🆕
```python
# app/api/events.py
# POST /api/v1/events/suggest - Sugerir evento
# GET /api/v1/events/suggested - Listar sugeridos (status: suggested)
# POST /api/v1/events/{id}/approve - Aprobar → Crear en Google Calendar
# POST /api/v1/events/{id}/reject - Rechazar
# GET /api/v1/events - Listar todos
```

#### 1.6 Frontend para Eventos 🆕
```html
# static/events.html
# - Listar eventos sugeridos con relevancia
# - Vista de aprobación: título, fecha, lugar, descripción, imagen
# - Botones: Aprobar (→ Calendar) | Rechazar | Modificar
```

---

## 💡 Casos de Uso Reales

### **Caso 1: Evento desde Email**
```
1. Usuario recibe email: "Conferencia de IA el 15 de enero en Madrid - https://..."
2. Agente detecta email con información de evento (usando IMAP)
3. Extrae URL del evento
4. Scrapea la página del evento (web_scraping_tool)
5. EventAgent genera resumen y determina relevancia
6. Crea evento sugerido (extracted_events, status: suggested)
7. Usuario ve en frontend y aprueba
8. Se crea en Google Calendar (calendar_tool existente)
```

### **Caso 2: Evento desde Noticia** ⭐ NUEVO
```
1. Agente scrapea noticias relevantes (news_scraping_tool)
2. Encuentra: "OpenAI anuncia conferencia GPT-5 en San Francisco el 20 de marzo"
3. Extrae información del evento de la noticia
4. Determina relevancia (usuario interesado en IA → alta relevancia)
5. Crea evento sugerido
6. Usuario aprueba → Google Calendar
```

### **Caso 3: Evento desde Sitio Web**
```
1. Agente scrapea Eventbrite/Meetup (event_site_scraping_tool)
2. Filtra eventos relevantes usando RAG
3. Crea eventos sugeridos
4. Usuario revisa y aprueba los relevantes
```

---

## 🛠️ Implementación Técnica

### **Usar Tabla Existente: extracted_events**

**Ventajas**:
- ✅ Ya existe y está integrada
- ✅ Tiene todos los campos necesarios
- ✅ Ya tiene status: 'proposed' | 'confirmed' | 'created'
- ✅ Compatible con el flujo actual

**Adaptación**:
```sql
-- Añadir columna de relevancia (opcional)
ALTER TABLE extracted_events 
ADD COLUMN IF NOT EXISTS relevance_score FLOAT;

-- Usar status existente:
-- 'proposed' → eventos sugeridos (nuestro caso)
-- 'confirmed' → eventos aprobados por usuario
-- 'created' → eventos creados en Calendar
```

### **O Crear Tabla Nueva: events_suggested**

**Ventajas**:
- Separación clara entre eventos extraídos de emails vs eventos descubiertos
- Más campos específicos para eventos sugeridos

**Estructura**:
```sql
CREATE TABLE events_suggested (
  id UUID PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  start_at TIMESTAMPTZ,
  end_at TIMESTAMPTZ,
  location TEXT,
  source_url TEXT,
  image_url TEXT,
  relevance_score FLOAT,  -- Score de relevancia (0-1)
  source TEXT,  -- email | news | website | manual
  status TEXT DEFAULT 'suggested',  -- suggested | approved | rejected | created
  created_at TIMESTAMPTZ DEFAULT NOW(),
  ...
);
```

**Recomendación**: Usar `extracted_events` existente para mantener consistencia.

---

## 🎯 Próximos Pasos Inmediatos

### **Opción A: EventAgent + News Scraping** ⭐ RECOMENDADO
1. Crear `EventAgent` que use `web_scraping_tool` existente
2. Crear `news_scraping_tool` para descubrir eventos en noticias
3. Añadir endpoints para eventos sugeridos
4. Frontend básico

### **Opción B: Event Extraction de Emails**
1. Extender `imap_search_tool` para filtrar emails de eventos
2. Usar `url_extraction_tool` para extraer URLs
3. Procesar con `EventAgent`
4. Crear eventos sugeridos

### **Opción C: Híbrido** (Más completo)
1. EventAgent
2. News Scraping Tool
3. Event Extraction de Emails
4. Todo integrado

---

## 📊 Estado Actual vs Necesario

| Componente | Estado Actual | Adaptación Necesaria |
|------------|---------------|----------------------|
| **Web Scraping** | ✅ `web_scraping_tool` creado | Usar directamente |
| **URL Extraction** | ✅ `url_extraction_tool` creado | Usar directamente |
| **IMAP/Gmail** | ✅ `imap_search_tool`, `imap_read_tool` | Extender para eventos |
| **Google Calendar** | ✅ `calendar_tool` existe | Usar para crear eventos aprobados |
| **extracted_events** | ✅ Tabla existe | Usar para eventos sugeridos |
| **EventAgent** | ❌ No existe | Crear (adaptado de ContentAgent) |
| **News Scraping** | ❌ No existe | Crear (nueva idea) |
| **API Events** | ❌ No existe | Crear (adaptado de posts.py) |
| **Frontend Events** | ❌ No existe | Crear (adaptado de posts.html) |

---

## 🚀 Roadmap Priorizado Adaptado

### **Sprint 1: EventAgent + API** (2-3 días)

1. **EventAgent** (2 horas)
   - Usar `web_scraping_tool` para obtener contenido
   - Generar resumen con LLM
   - Determinar relevancia con RAG
   - Retornar estructura compatible con `extracted_events`

2. **API Endpoints** (1 hora)
   - `POST /api/v1/events/suggest`
   - `GET /api/v1/events/suggested`
   - `POST /api/v1/events/{id}/approve` → Google Calendar
   - `POST /api/v1/events/{id}/reject`

3. **Frontend básico** (1 hora)
   - `static/events.html`
   - Listar eventos sugeridos
   - Botones de aprobación

### **Sprint 2: Fuentes de Eventos** (2-3 días)

1. **News Scraping Tool** (3 horas) ⭐
   - Scrapear noticias configurables
   - Extraer eventos mencionados
   - Determinar relevancia

2. **Event Extraction de Emails** (2 horas)
   - Filtrar emails con eventos
   - Extraer URLs y fechas
   - Procesar con EventAgent

---

## 💡 Ideas Específicas para Web Scraping

### **1. News Scraping para Eventos** ⭐

**Propósito**: Descubrir eventos mencionados en noticias relevantes

**Implementación**:
```python
# app/agents/tools/news_scraping_tool.py
class NewsScrapingTool(BaseTool):
    async def execute(self, sites: List[str], keywords: List[str]):
        # Scrapear sitios de noticias
        # Buscar menciones de eventos usando keywords
        # Extraer información del evento
        # Retornar eventos encontrados
```

**Sitios configurables**:
- TechCrunch, HackerNews (para eventos de tech)
- Sitios de noticias de la industria del usuario
- Blogs relevantes

**Ejemplo**:
```
Noticia: "OpenAI anuncia conferencia GPT-5 en San Francisco el 20 de marzo"
→ Agente extrae: evento, fecha, lugar
→ Determina relevancia (usuario interesado en IA)
→ Crea evento sugerido
```

### **2. Event Site Scraping**

**Sitios a scrapear**:
- Eventbrite (eventos locales)
- Meetup (grupos de interés)
- Sitios de conferencias específicas

**Implementación**:
```python
# Extender web_scraping_tool
# Detectar si es página de evento
# Extraer información estructurada de eventos
```

---

## ✅ Lo que YA podemos usar

1. ✅ **web_scraping_tool** - Para scrapear páginas de eventos
2. ✅ **url_extraction_tool** - Para extraer URLs de emails
3. ✅ **imap_search_tool** - Para leer emails
4. ✅ **calendar_tool** - Para crear eventos en Google Calendar
5. ✅ **extracted_events** - Tabla para almacenar eventos sugeridos
6. ✅ **RAG** - Para determinar relevancia
7. ✅ **Multi-Agente** - Para orquestar el flujo

---

## 🎯 Decisión: ¿Qué implementamos primero?

### **Opción A: EventAgent + News Scraping** ⭐ RECOMENDADO
- EventAgent procesa URLs de eventos
- News Scraping Tool para descubrir eventos en noticias
- Más útil y diferenciado

### **Opción B: EventAgent + Email Extraction**
- Usar IMAP existente
- Extraer eventos de emails
- Más directo

### **Opción C: Todo junto**
- EventAgent + News Scraping + Email Extraction
- Máxima cobertura

---

**¿Con cuál seguimos?** 🚀




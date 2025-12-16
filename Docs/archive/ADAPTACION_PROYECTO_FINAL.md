# 🎯 Adaptación del Proyecto Final al Event Manager

**Fecha**: Diciembre 2025  
**Proyecto Real**: Personal Coordination Voice Agent (Event Manager)  
**Proyecto Final del Curso**: Agente IA para Curación de Contenidos (MOLDE/PLANTILLA)

---

## 💡 Entendimiento del Proyecto

### **Proyecto del Curso (Molde)**
- Monitorizar Telegram/WhatsApp → Extraer URLs → Procesar → Publicar en web
- **Técnicas**: MCP, Web Scraping, Human-in-the-Loop, Multi-Agente

### **Nuestro Proyecto Real (Event Manager)**
- **Objetivo**: Gestión inteligente de eventos personales
- **Ya tenemos**: Google Calendar, Gmail, Calendly, WhatsApp, RAG, Voz
- **Necesitamos**: Adaptar las técnicas del curso a nuestro caso de uso

---

## 🔄 Adaptación: De "Curación de Contenidos" a "Event Manager Inteligente"

### **Idea Central**: 
En lugar de monitorizar Telegram/WhatsApp para URLs genéricas, usamos las mismas técnicas para:
1. **Monitorear emails de Gmail** para información de eventos
2. **Web scraping** para sitios de eventos/conferencias relevantes
3. **Procesar y sugerir eventos** al usuario
4. **Human-in-the-Loop** para aprobar eventos sugeridos

---

## 🎯 Propuesta: "Event Discovery & Curation Agent"

### **Flujo Adaptado**:

```
┌─────────────────────────────────────────────────────────┐
│  1. MONITORIZACIÓN (Equivalente a Telegram/WhatsApp)   │
│     - Gmail: Leer emails con información de eventos     │
│     - Google Calendar: Detectar eventos nuevos          │
│     - Web: Scrapear sitios de eventos/conferencias      │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  2. EXTRACCIÓN (Equivalente a extraer URLs)              │
│     - Extraer URLs de eventos de emails                 │
│     - Extraer fechas, lugares, descripciones            │
│     - Identificar eventos relevantes para el usuario    │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  3. PROCESAMIENTO (Equivalente a procesar URLs)         │
│     - Scrapear páginas de eventos                       │
│     - Extraer: título, fecha, lugar, descripción        │
│     - Generar resumen del evento                        │
│     - Determinar relevancia (usando RAG + preferencias) │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  4. HUMAN-IN-THE-LOOP (Aprobación)                      │
│     - Mostrar eventos sugeridos                        │
│     - Usuario aprueba/rechaza/modifica                 │
│     - Si aprueba → Crear en Google Calendar             │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  5. ALMACENAMIENTO (Equivalente a publicar en web)      │
│     - Guardar en Supabase (tabla events_suggested)      │
│     - Si aprobado → Crear en Google Calendar            │
│     - Frontend para ver eventos sugeridos               │
└─────────────────────────────────────────────────────────┘
```

---

## 🛠️ Implementación Adaptada

### **1. Monitorización Adaptada** (En lugar de Telegram/WhatsApp)

#### **Opción A: Gmail para Eventos** ✅ (Ya tenemos IMAP)
```python
# Usar IMAP existente para leer emails
# Filtrar emails que mencionen eventos/conferencias
# Extraer URLs de eventos de emails
# Ya tenemos: app/agents/tools/imap_search_tool.py
```

#### **Opción B: Web Scraping de Sitios de Eventos** 🆕
```python
# Scrapear sitios relevantes para el usuario:
# - Eventbrite, Meetup, Conferencias locales
# - Sitios de eventos de la industria del usuario
# - Calendarios públicos de eventos
```

#### **Opción C: Google Calendar Webhooks** ✅ (Ya tenemos)
```python
# Ya tenemos webhooks de Calendly
# Podemos extender para detectar eventos nuevos
```

### **2. Extracción Adaptada** (En lugar de solo URLs)

#### **Event Extraction Tool** 🆕
```python
# app/agents/tools/event_extraction_tool.py
# - Extraer URLs de eventos de emails
# - Extraer fechas, lugares, descripciones de texto
# - Usar RAG para determinar relevancia
# - Similar a url_extraction_tool pero específico para eventos
```

### **3. Procesamiento Adaptado** (Web Scraping para Eventos)

#### **Event Scraping Tool** 🆕 (Basado en web_scraping_tool)
```python
# app/agents/tools/event_scraping_tool.py
# Extiende web_scraping_tool pero especializado en eventos:
# - Extrae: título, fecha, hora, lugar, descripción
# - Detecta tipo de evento (conferencia, meetup, workshop)
# - Extrae información de registro/inscripción
# - Determina si el evento es relevante (usando RAG)
```

### **4. ContentAgent Adaptado → EventAgent** 🆕

```python
# app/agents/specialists/event_agent.py
# En lugar de ContentAgent genérico, un EventAgent especializado:
# - Procesa URLs de eventos
# - Genera resumen del evento (2-3 líneas)
# - Determina relevancia usando RAG + preferencias del usuario
# - Sugiere si el usuario debería asistir
# - Retorna estructura de evento sugerido
```

### **5. Human-in-the-Loop Adaptado**

#### **Event Approval System** 🆕
```python
# app/api/events.py (en lugar de posts.py)
# GET /api/v1/events/suggested - Eventos sugeridos
# POST /api/v1/events/{id}/approve - Aprobar → Crear en Calendar
# POST /api/v1/events/{id}/reject - Rechazar
# POST /api/v1/events/{id}/modify - Modificar detalles
```

### **6. Almacenamiento Adaptado**

#### **Tabla events_suggested** (En lugar de posts)
```sql
-- Similar a posts pero para eventos
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
  status TEXT DEFAULT 'suggested', -- suggested | approved | rejected | created
  created_at TIMESTAMPTZ DEFAULT NOW(),
  ...
);
```

---

## 🎨 Casos de Uso Reales para Event Manager

### **Caso 1: Descubrimiento de Eventos desde Emails**
```
1. Usuario recibe email: "Conferencia de IA el 15 de enero en Madrid"
2. Agente detecta email con información de evento
3. Extrae URL del evento del email
4. Scrapea la página del evento
5. Genera resumen y determina relevancia
6. Sugiere evento al usuario
7. Usuario aprueba → Se crea en Google Calendar
```

### **Caso 2: Monitoreo de Sitios de Eventos**
```
1. Agente scrapea periódicamente sitios relevantes:
   - Eventbrite (eventos locales)
   - Meetup (grupos de interés)
   - Sitios de conferencias de la industria
2. Filtra eventos relevantes usando RAG + preferencias
3. Crea eventos sugeridos
4. Usuario revisa y aprueba los relevantes
```

### **Caso 3: Noticias Relevantes para Eventos** 🆕
```
1. Agente scrapea noticias/artículos relevantes
2. Identifica eventos mencionados en noticias
3. Extrae información del evento
4. Sugiere al usuario eventos que podrían interesarle
```

### **Caso 4: Consolidación de Eventos**
```
1. Agente detecta eventos duplicados o similares
2. Sugiere consolidar eventos relacionados
3. Usuario decide qué hacer
```

---

## 🚀 Plan de Implementación Adaptado

### **FASE 1: Fundamentos Adaptados** (3-4 días)

#### 1.1 Tabla events_suggested en Supabase ✅
```sql
-- Similar a posts pero para eventos
-- Ya tenemos extracted_events, podemos extender o crear nueva tabla
```

#### 1.2 Event Extraction Tool 🆕
```python
# app/agents/tools/event_extraction_tool.py
# - Extraer URLs de eventos de emails
# - Extraer fechas, lugares de texto
# - Usar regex + NLP básico
```

#### 1.3 Event Scraping Tool 🆕 (Basado en web_scraping_tool)
```python
# app/agents/tools/event_scraping_tool.py
# Extiende web_scraping_tool pero especializado:
# - Detecta estructura de páginas de eventos
# - Extrae: fecha, hora, lugar, descripción
# - Identifica tipo de evento
```

#### 1.4 EventAgent 🆕 (En lugar de ContentAgent)
```python
# app/agents/specialists/event_agent.py
# - Procesa URLs de eventos
# - Genera resumen con LLM
# - Determina relevancia usando RAG
# - Retorna evento sugerido
```

#### 1.5 API Endpoints para Eventos 🆕
```python
# app/api/events.py
# POST /api/v1/events/suggest - Sugerir evento
# GET /api/v1/events/suggested - Listar sugeridos
# POST /api/v1/events/{id}/approve - Aprobar → Calendar
# POST /api/v1/events/{id}/reject - Rechazar
```

#### 1.6 Frontend para Eventos 🆕
```html
# static/events.html
# - Listar eventos sugeridos
# - Vista de aprobación
# - Mostrar: título, fecha, lugar, descripción, relevancia
```

---

## 💡 Ideas Específicas para Web Scraping en Event Manager

### **1. Scraping de Noticias Relevantes** ⭐ NUEVA IDEA

**Propósito**: Leer noticias/artículos y extraer eventos mencionados

**Implementación**:
```python
# app/agents/tools/news_scraping_tool.py
# - Scrapea sitios de noticias relevantes (configurables)
# - Busca menciones de eventos/conferencias
# - Extrae información del evento
# - Determina si es relevante para el usuario
```

**Casos de uso**:
- Noticias de tecnología → Eventos de tech
- Noticias de la industria del usuario → Eventos relevantes
- Artículos de blogs → Eventos mencionados

**Ejemplo**:
```
Noticia: "OpenAI anuncia conferencia GPT-5 en San Francisco el 20 de marzo"
→ Agente extrae: evento, fecha, lugar
→ Determina relevancia (usuario interesado en IA)
→ Sugiere evento al usuario
```

### **2. Scraping de Sitios de Eventos Específicos**

**Sitios a scrapear** (configurables):
- Eventbrite (eventos locales)
- Meetup (grupos)
- Sitios de conferencias específicas
- Calendarios públicos de eventos

**Implementación**:
```python
# app/agents/tools/event_site_scraping_tool.py
# - Scrapea sitios específicos de eventos
# - Filtra por categorías relevantes
# - Extrae información estructurada
```

### **3. Scraping de Páginas de Eventos Individuales**

**Cuando el usuario comparte una URL de evento**:
```python
# Ya tenemos web_scraping_tool
# Extender para detectar si es página de evento
# Extraer información específica de eventos
```

---

## 🎯 Matriz de Adaptación: Curso → Event Manager

| Técnica del Curso | Adaptación para Event Manager | Estado |
|-------------------|-------------------------------|--------|
| **Monitorizar Telegram/WhatsApp** | Monitorizar Gmail + Web scraping sitios eventos | ⏳ Pendiente |
| **Extraer URLs** | Extraer URLs de eventos + fechas/lugares | ✅ URL tool listo |
| **Procesar URLs** | Scrapear páginas de eventos | ✅ Web scraping listo |
| **Generar resumen** | Generar resumen de evento | ⏳ Pendiente (EventAgent) |
| **Human-in-the-Loop** | Aprobar eventos sugeridos | ⏳ Pendiente |
| **Publicar en web** | Crear en Google Calendar | ✅ Calendar tool existe |
| **Scheduling** | Monitoreo periódico de eventos | ⏳ Pendiente |

---

## 🚀 Roadmap Adaptado para Event Manager

### **FASE 1: Event Discovery MVP** (3-4 días)

#### 1.1 Tabla events_suggested ✅
- Similar a posts pero para eventos
- Campos: title, description, start_at, end_at, location, source_url, relevance_score, status

#### 1.2 Event Extraction Tool 🆕
- Extraer URLs de eventos de emails
- Extraer fechas/lugares de texto
- Usar IMAP existente

#### 1.3 Event Scraping Tool 🆕
- Extender web_scraping_tool
- Especializado en páginas de eventos
- Extrae: fecha, hora, lugar, descripción

#### 1.4 EventAgent 🆕
- Procesa URLs de eventos
- Genera resumen con LLM
- Determina relevancia (RAG + preferencias)
- Retorna evento sugerido

#### 1.5 API Endpoints 🆕
- `POST /api/v1/events/suggest` - Sugerir evento
- `GET /api/v1/events/suggested` - Listar sugeridos
- `POST /api/v1/events/{id}/approve` - Aprobar → Calendar
- `POST /api/v1/events/{id}/reject` - Rechazar

#### 1.6 Frontend 🆕
- `static/events.html` - Ver eventos sugeridos
- Vista de aprobación con detalles del evento

---

## 💡 Ideas Adicionales para Event Manager

### **1. News Scraping para Eventos** ⭐
```python
# Scrapear noticias relevantes
# Extraer eventos mencionados
# Sugerir eventos al usuario
```

**Ejemplo de uso**:
- Usuario interesado en "Machine Learning"
- Agente scrapea noticias de ML
- Encuentra: "Conferencia NeurIPS 2025 en Vancouver"
- Extrae información del evento
- Sugiere al usuario

### **2. Event Relevance Scoring**
```python
# Usar RAG para determinar relevancia
# Comparar evento con:
# - Preferencias del usuario (almacenadas en RAG)
# - Eventos anteriores del usuario
# - Intereses detectados de emails/calendario
```

### **3. Event Deduplication**
```python
# Detectar eventos duplicados o similares
# Consolidar sugerencias
# Evitar spam de eventos similares
```

### **4. Smart Event Suggestions**
```python
# Basado en:
# - Eventos anteriores del usuario
# - Preferencias detectadas
# - Ubicación del usuario
# - Disponibilidad en calendario
```

---

## 🎯 Próximos Pasos Adaptados

### **Opción 1: Continuar con EventAgent** (Recomendado)
1. Crear `EventAgent` (similar a ContentAgent pero para eventos)
2. Usar `web_scraping_tool` existente
3. Añadir lógica de relevancia usando RAG
4. Generar resumen de evento con LLM

### **Opción 2: News Scraping Tool** (Nueva idea)
1. Crear `news_scraping_tool.py`
2. Scrapear sitios de noticias configurables
3. Extraer eventos mencionados
4. Determinar relevancia

### **Opción 3: Event Extraction de Emails**
1. Extender `imap_search_tool` existente
2. Filtrar emails con información de eventos
3. Extraer URLs y fechas
4. Procesar con EventAgent

---

## 📊 Comparación: Proyecto Curso vs Event Manager

| Aspecto | Proyecto Curso (Molde) | Event Manager (Nuestro) |
|---------|------------------------|-------------------------|
| **Fuente** | Telegram/WhatsApp | Gmail + Web scraping |
| **Extracción** | URLs genéricas | URLs de eventos + fechas/lugares |
| **Procesamiento** | Contenido web genérico | Páginas de eventos específicas |
| **Output** | Posts para web | Eventos sugeridos |
| **Aprobación** | Publicar en web | Crear en Google Calendar |
| **Almacenamiento** | Tabla posts | Tabla events_suggested |
| **Frontend** | Visualizar posts | Ver eventos sugeridos |

---

## ✅ Lo que YA tenemos que podemos usar

1. ✅ **IMAP/Gmail**: Ya tenemos `imap_search_tool` y `imap_read_tool`
2. ✅ **Google Calendar**: Ya tenemos `calendar_tool` para crear eventos
3. ✅ **Web Scraping**: Acabamos de crear `web_scraping_tool`
4. ✅ **URL Extraction**: Ya tenemos `url_extraction_tool`
5. ✅ **RAG**: Ya tenemos RAG para determinar relevancia
6. ✅ **Multi-Agente**: Ya tenemos arquitectura LangGraph

---

## 🎯 Decisión: ¿Qué implementamos primero?

### **Opción A: EventAgent + News Scraping** ⭐ RECOMENDADO
- EventAgent procesa URLs de eventos
- News Scraping Tool para descubrir eventos en noticias
- Más útil para el usuario final

### **Opción B: Event Extraction de Emails**
- Usar IMAP existente
- Extraer eventos de emails
- Más directo, menos scraping

### **Opción C: Híbrido**
- EventAgent + News Scraping + Email extraction
- Máxima cobertura de fuentes

---

**¿Con cuál opción seguimos?** 🚀




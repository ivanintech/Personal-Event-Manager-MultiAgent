# 🧠 Presentación Técnica — Personal Coordination Voice Agent

Este documento guía una **presentación viva** del proyecto final del curso _Agentes IA 2ª Edición_. Resume qué mostrar, dónde está el código y qué logs/diagramas enseñar para evidenciar las capacidades técnicas: MCP, Function Calling, LangGraph, RAG, voz y multi-agente.

---

## 1. Apertura y contexto ("¿Qué estamos presentando?")

- “Este agente es la suma práctica de los días del curso: MCP, Function Calling y arquitecturas multi-agente.”
- “En la demo vemos tres capas: voz, orquestación multi-agente y ejecución de herramientas (MCP/local), y cómo se visualiza todo en el frontend.”
- Objetivo: convertir conversación de voz en acciones reales (calendario, correos, WhatsApp, Calendly) con trazabilidad completa en modo desarrollador.

## 2. Arquitectura general (citar `docs/diagrams/arquitectura_componentes.svg`)

- **Capa de voz (WebSocket + VAD)**  
  • STT (Groq Whisper) y TTS (VibeVoice + Web Speech API) con interrupciones.  
  • Modo desarrollador muestra “AUDIO”, “STT”, “DEV” en burbujas grises.
- **Orquestador multi-agente**  
  • Pipeline RAG → Agent → Tool → Humanización (limpieza `_strip_think`, `_humanize_response`).  
  • Logs por iteración: `agent_llm_reasoning`, `agent_tools_available`, `agent_cleaning_response`, `agent_response_ready`.  
  • Burbujas dev con tipo de agente (CAL, EMAIL, SCHED, COMMS, GEN, ORCH).
- **Herramientas / MCP**  
  • Registro único (`tool_registry`) con 14 tools (Google Calendar, IMAP, Calendly, WhatsApp, scraping).  
  • MCP manager gestiona clientes WebSocket/HTTP/stdio y soporta mock/local.  
  • Definiciones function-calling en `tool_schemas.py` (OpenAI/Anthropic/Nebius).

### Rutas clave de código para mostrar

- `app/agents/orchestrator.py` → loop agentic, limpieza de `<think>`, routing de intención, filtrado de tools.
- `app/agents/graph.py` → LangGraph (entry → intent → rag → policy → agent → plan → tool → response).
- `app/schemas/tool_schemas.py` → definiciones de tools expuestas al LLM.
- `app/agents/tools/*.py` → implementación de cada tool (IMAP, Calendly, WhatsApp, scraping).
- `app/mcp/manager.py` y `app/mcp/clients/*` → clientes MCP y pooling.
- `static/events_voice.html` → frontend, modo dev, panel de sugerencias, interrupciones TTS.
- `docs/diagrams/*.svg` → diagramas de arquitectura, flujo de voz y LangGraph.

### Snippets rápidos para enseñar sin navegar

- **Routing + filtrado de tools** (`orchestrator.py`):

```python
intent = detect_intent(query)
agent_type = agent_type_map.get(intent, "General Agent")
filtered_tools = get_tools_for_agent(agent_type)
response = await self._call_llm_with_tools(messages, tools=filtered_tools)
```

- **Tool calling OpenAI/Nebius** (function-calling):

```python
response = self.client.chat.completions.create(
    model=self.model,
    messages=messages,
    tools=tools_to_use,
    tool_choice="auto",
)
```

- **Limpieza de `&lt;think&gt;` + humanización** (`_strip_think`, `_humanize_response`):

```python
cleaned = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.S|re.I)
clean_text = self._humanize_response(cleaned, tool_calls, citations, tool_results)
```

- **Dev logs** (ejemplos): `agent_llm_reasoning`, `agent_tools_detected`, `agent_response_ready`.

- **LangGraph** (`graph.py`, nodes principales):

```python
def build_graph():
    # entry -> intent -> rag -> policy -> agent -> plan -> tool -> response -> END
    graph = StateGraph(AgentState)

    async def node_intent(state):
        llm_int = await llm_intent_router_llm(state["user_query"])
        intent_value = llm_int or intent_router(state["user_query"])
        return {"intent": intent_value, "agent": agent_map[intent_value]}
```

- **Definición de tools expuestas al LLM** (`tool_schemas.py`):

```python
TOOL_DEFINITIONS = [
    {"type": "function", "function": {
        "name": "list_agenda_events",
        "description": "Lista citas en Supabase",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}}
    }},
    # ... create_calendar_event, search_emails, read_email,
    # create/list/ingest_calendly_events, send_whatsapp, scrape_news_for_events ...
]
```

## 3. Flujo de voz + RAG

- **Diagrama `docs/diagrams/flujo_voz_completo.svg`**  
  1. VAD detecta audio → WebM → WAV (ffmpeg requerido → logs si falta).  
  2. STT (Groq Whisper) transcribe y muestra el texto inmediatamente.  
  3. Validación rápida filtra ruido/no-sentido y reinicia escucha.  
  4. Feedback inmediato: el frontend publica la transcripción y permite interrumpir TTS.  
  5. Respuesta: el agente genera `<think>`, limpia con `_strip_think()` y humaniza con `_humanize_response()`.

## 4. Sistema multi-agente y LangGraph

- Intent Routing (`detect_intent()` en `orchestrator.py`) decide agente:  
  CAL (calendario), EMAIL (IMAP), SCHED (Calendly), COMMS (WhatsApp), GEN (fallback), ORCH (coordinador).  
- Filtrado de herramientas por agente (`get_tools_for_agent()`) evita invocar tools fuera de dominio.  
- LangGraph (`docs/diagrams/langgraph_flow.svg`, `app/agents/graph.py`) muestra entry → intent → rag → policy → agent → plan → tool → response.  
- Logs dev separan el `<think>` de cada agente en burbujas grises; nombres cortos (CAL/EMAIL/SCHED/COMMS/GEN/ORCH) en el avatar.
- Prompts: `_build_initial_messages` arma el system prompt con fecha actual, capacidades y contexto RAG; incluye instrucciones de tool use y cites.  
- Conexión agents-tools:  
  • LLM recibe `tools=TOOL_DEFINITIONS` filtradas.  
  • El LLM devuelve `tool_calls`; el orquestador ejecuta vía `execute_tool` (MCP → fallback local) y retroalimenta otra iteración.  
  • Cuando `tool_results` traen texto formateado, se prioriza en la respuesta final y se humaniza antes de enviar al usuario.

## 5. MCP y protocolos

- MCP Protocol: tools IMAP/Calendly/WhatsApp/Calendar vía JSON-RPC 2.0; `MCPClientManager` mantiene pool y reintentos; `execute_tool()` intenta MCP y cae a `tool_registry` si falla; IMAP usa cliente directo para evitar recursión.
- Tool definitions en `tool_schemas.py`: `search_emails`, `read_email`, `create_calendly_event`, `list_calendly_events`, `ingest_calendly_events`, `send_whatsapp`, `scrape_news_for_events`, además de calendario, email, scraping.

## 6. Casos relevantes y logs

- WhatsApp: `send_whatsapp` con fallback si Twilio no tiene credenciales.  
- Calendly: `list/create/ingest` con OAuth + refresh.  
- Email: `search_emails` y `read_email` con IMAP y solución a recursión.  
- Logs clave: `agent_llm_reasoning`, `agent_tools_detected`, `agent_tools_available`, `agent_response_ready`.  
- Modo dev (toggle ON por defecto) muestra toda la cadena como burbujas grises con tipo de agente.

## 7. Referencias al curso `CursoAgentesIA.txt`

- Día 1: MCP y clientes.  
- Día 2: Function Calling (OpenAI, Anthropic, Nebius) + RAG con Supabase.  
- Día 3: Multi-agente, LangGraph, handoff y orchestrator.  
- Día 4-5: Voz, VAD, interrupciones, TTS, Web Speech API y Dev-mode.  
- Día 6+: Integraciones externas (Calendly, WhatsApp) configurables vía MCP.  
- “Altas capacidades”: RAG + voz + multi-agente + herramientas + logging completo para auditoría.

## 8. Cierre y siguientes pasos

- Mostrar panel de eventos sugeridos (12 ejemplos) y cómo interrumpen el flujo actual.  
- Recordar que el micro se reactiva tras la respuesta y que la TTS tiene fallback automático.  
- Invitar a probar: crear evento, confirmarlo, leer email, mandar WhatsApp, ejecutar Calendly, abrir panel dev.  
- Retos siguientes: integrar LiveKit Agents (Piper/XTTS/Whisper), añadir nuevos tools MCP, generar diagramas personalizados.

---

> **Notas para el presentador**  
>
> - Arranca en modo Dev para mostrar las burbujas grises.  
> - Muestra diagramas SVG en `docs/diagrams/` (Arquitectura, LangGraph, Flujo de voz, Multi-agente).  
> - Si preguntan por fallos, cita trazas: ffmpeg ausente, VibeVoice code=1006 (fallback TTS), recursión IMAP resuelta.

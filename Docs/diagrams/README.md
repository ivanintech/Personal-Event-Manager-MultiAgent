# 📊 Diagramas del Sistema

Esta carpeta contiene diagramas SVG que visualizan la arquitectura y flujos del sistema.

## Diagramas Disponibles

### 1. `arquitectura_componentes.svg`

**Arquitectura de Componentes Principales**

Muestra la arquitectura completa del sistema en capas:
- **Frontend Layer**: Voice Interface con VAD, Web Speech API, Modo Desarrollador
- **WebSocket Layer**: Comunicación bidireccional (STT, TTS, Logs, Interrupciones)
- **Orchestrator Layer**: Multi-Agent Orchestrator con RAG, LLM, Agentes Especializados, Humanización
- **MCP Layer**: Model Context Protocol con transportes y servidores MCP
- **External Services**: Servicios externos integrados

**Uso**: Ideal para presentaciones generales del sistema y explicar la arquitectura de alto nivel.

---

### 2. `langgraph_flow.svg`

**Flujo LangGraph - Sistema Multi-Agente**

Visualiza el grafo de LangGraph con todos sus nodos y el flujo de estado:
- **ENTRY** → **INTENT** → **RAG** → **CONFLICT_CHECK** → **POLICY** → **AGENT** → **PLAN** → **TOOL** → **RESPONSE** → **END**

Incluye:
- Descripción de cada nodo
- Flujo de datos (AgentState)
- Tipos de agentes especializados
- Decisiones de routing

**Uso**: Perfecto para explicar el patrón orquestador y cómo funciona el sistema multi-agente internamente.

---

### 3. `flujo_voz_completo.svg`

**Flujo Completo de Voz: STT → Agent → TTS**

Detalla todo el proceso de interacción por voz:
1. Usuario habla (VAD)
2. Conversión de audio (WebM → WAV)
3. STT (Speech-to-Text con Whisper)
4. Validación de mensaje
5. Procesamiento del agente (RAG, LLM, Tools, Humanización)
6. TTS (VibeVoice primario, Web Speech API fallback)
7. Reproducción de audio
8. Reactivación del micrófono

Incluye:
- Interrupciones (usuario puede interrumpir al agente)
- Fallbacks automáticos
- Flujo de reactivación

**Uso**: Excelente para explicar cómo funciona la interfaz de voz y el sistema de interrupciones.

---

### 4. `sistema_multiagente_mcp.svg`

**Sistema Multi-Agente con MCP**

Muestra cómo el orquestador coordina agentes especializados y cómo se comunican con servidores MCP:
- **Orchestrator Agent (ORCH)**: Coordinador principal
- **Agentes Especializados**: Calendar (CAL), Email (EMAIL), Scheduling (SCHED), WhatsApp (WA)
- **MCP Layer**: Protocolo estándar con transportes (stdio, HTTP, HTTP+SSE, OAuth, REST)
- **Servidores MCP**: google-calendar, imap, calendly, whatsapp, filesystem, google-drive, mock
- **Tool Registry**: Sistema centralizado de herramientas

**Uso**: Ideal para demostrar la integración MCP y cómo los agentes usan herramientas externas.

---

## Cómo Usar los Diagramas

### Visualización

Los diagramas SVG se pueden visualizar de varias formas:

1. **En el navegador**: Abre directamente el archivo `.svg` en cualquier navegador moderno
2. **En Markdown**: Los diagramas están referenciados en el README principal
3. **En presentaciones**: Puedes importarlos en PowerPoint, Keynote, o herramientas de diseño
4. **En documentación**: Úsalos en documentación técnica o wikis

### Edición

Los diagramas están creados en SVG estándar y pueden editarse con:
- **Editores de texto**: Cualquier editor que soporte SVG
- **Herramientas de diseño**: Inkscape, Adobe Illustrator, Figma
- **Editores online**: draw.io, Excalidraw

### Conversión a Otros Formatos

Si necesitas convertir los SVG a otros formatos:

```bash
# Convertir a PNG (requiere Inkscape)
inkscape --export-type=png --export-dpi=300 diagrama.svg

# Convertir a PDF (requiere Inkscape)
inkscape --export-type=pdf diagrama.svg

# Convertir a JPG (requiere ImageMagick)
convert -density 300 diagrama.svg diagrama.jpg
```

---

## Notas Técnicas

- **Formato**: SVG (Scalable Vector Graphics) - escalable sin pérdida de calidad
- **Tamaño**: Optimizado para visualización en pantalla (1200-1400px de ancho)
- **Colores**: Usan gradientes y colores consistentes para mejor legibilidad
- **Fuentes**: Arial (fallback a sans-serif) para compatibilidad universal

---

## Contribuciones

Si creas nuevos diagramas o mejoras los existentes:
1. Mantén el estilo visual consistente
2. Usa los mismos gradientes y colores
3. Incluye descripciones claras en cada componente
4. Actualiza este README con la descripción del nuevo diagrama



# Directory: yt-agentic-rag/app/agents/orchestrator.py

"""
Agent Orchestrator - The Core of Agentic RAG.

This module implements the main agent reasoning loop:
    Query → RAG Retrieve → Reason → Decide → Act (Tools) → Respond

The orchestrator combines:
- RAG context retrieval from Supabase vector database
- LLM reasoning with tool-calling capabilities (OpenAI/Anthropic)
- Tool execution via the tool registry
- Final response generation with citations

This is what makes "Agentic RAG" different from plain RAG - the agent
can reason about whether to use tools and execute real-world actions.
"""

import logging
import time
import json
import re
from typing import Dict, Any, List, Optional, Callable
import openai
import anthropic
import httpx

from ..config.settings import get_settings
from ..config.database import db
from ..services.embedding import embedding_service as default_embedding_service
from .tool_exec import execute_tool
from ..schemas.tool_schemas import TOOL_DEFINITIONS

logger = logging.getLogger(__name__)
settings = get_settings()


# Intent routing similar to LangGraph
class Intent:
    CALENDAR = "calendar"
    EMAIL = "email"
    SCHEDULING = "scheduling"
    COMMS = "comms"
    GENERAL = "general"


def detect_intent(query: str) -> str:
    """Detect user intent from query to route to appropriate agent."""
    q = query.lower()
    # SCHEDULING debe ir ANTES de CALENDAR para que "calendly" no se detecte como calendar
    # Verificar primero palabras clave específicas de Calendly
    if any(k in q for k in ["calendly", "crear evento en calendly", "evento en calendly", "consulta en calendly"]):
        return Intent.SCHEDULING
    # Email debe ir antes de calendar para evitar falsos positivos
    if any(k in q for k in ["email", "correo", "mail", "leer email", "buscar email", "último email", "emails sobre"]):
        return Intent.EMAIL
    # WhatsApp/Comms
    if any(k in q for k in ["whatsapp", "enviar mensaje por whatsapp", "mensaje de whatsapp"]):
        return Intent.COMMS
    # Calendar (pero no si ya detectamos Calendly)
    if any(k in q for k in ["calendar", "reunión", "cita", "meeting", "agendar", "evento en google calendar"]):
        return Intent.CALENDAR
    # Scheduling genérico (disponibilidad, etc.)
    if any(k in q for k in ["disponibilidad", "availability", "consultar disponibilidad"]):
        return Intent.SCHEDULING
    return Intent.GENERAL


def get_tools_for_agent(agent_type: str) -> List[Dict[str, Any]]:
    """Filter tools based on agent type."""
    # Mapeo de herramientas por agente
    agent_tools = {
        "Calendar Agent": [
            "list_agenda_events",
            "confirm_agenda_event",
            "list_cal_events",
            "create_calendar_event",
            "extract_urls",
            "scrape_web_content",
        ],
        "Email Agent": [
            "search_emails",
            "read_email",
            "send_email",
            "extract_urls",
            "scrape_web_content",
        ],
        "Scheduling Agent": [
            "create_calendly_event",
            "list_calendly_events",
            "ingest_calendly_events",
            "create_calendar_event",
            "list_agenda_events",
            "extract_urls",
        ],
        "Comms Agent": [
            "send_whatsapp",
            "send_email",
            "extract_urls",
        ],
        "General Agent": TOOL_DEFINITIONS,  # Todos los tools para el agente general
    }
    
    # Si el agente tiene herramientas específicas, filtrar
    if agent_type in agent_tools and agent_type != "General Agent":
        allowed_tools = agent_tools[agent_type]
        return [
            tool for tool in TOOL_DEFINITIONS
            if tool.get("function", {}).get("name") in allowed_tools
        ]
    
    # Por defecto, devolver todas las herramientas
    return TOOL_DEFINITIONS


class AgentService:
    """
    Main agent service that orchestrates the Agentic RAG pipeline.
    
    The agent follows this pipeline:
    1. Retrieve relevant context from RAG (Supabase vector search)
    2. Build messages with system prompt including RAG context
    3. Call LLM with tool definitions
    4. If LLM requests tool calls, execute them and loop back
    5. Generate final response with citations and tool results
    
    This allows the agent to both answer questions using RAG context
    AND take actions (schedule meetings, send emails) when needed.
    """
    
    def __init__(self, embedding_service=None, metrics_service=None):
        """
        Initialize the agent service with configured AI provider.
        
        Args:
            embedding_service: Optional embedding service (for dependency injection)
            metrics_service: Optional metrics service (for dependency injection)
        """
        self.provider = settings.ai_provider
        # Use injected services or fallback to global singletons for backward compatibility
        self.embedding_service = embedding_service if embedding_service is not None else default_embedding_service
        self._metrics_service = metrics_service
        
        if self.provider == "openai":
            self.client = openai.OpenAI(api_key=settings.openai_api_key)
            self.model = settings.openai_chat_model
        elif self.provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            self.model = settings.anthropic_chat_model
        elif self.provider == "nebius":
            self.client = None
            self.model = settings.nebius_chat_model
            self.base_url = settings.nebius_base_url.rstrip("/")
            self.api_key = settings.nebius_api_key
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")
        
        logger.info(
            f"Agent service initialized with {self.provider} ({self.model})"
        )
    
    async def process_query(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        user_id: Optional[str] = None,
        top_k: int = 6,
        max_iterations: int = 5,
        log_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Process a user query through the full agentic pipeline.
        
        Args:
            query: User's question or action request
            chat_history: Optional list of previous messages for context
            user_id: Optional user identifier for personalization
            top_k: Number of RAG chunks to retrieve
            max_iterations: Maximum tool call iterations to prevent infinite loops
            log_callback: Optional callback function(event, data) to send logs to frontend
            
        Returns:
            Dict containing:
            - text: Final response text
            - tool_calls: List of tool calls made
            - tool_results: Results from tool executions
            - citations: RAG chunk IDs cited in response
            - debug: Debug information
        """
        start_time = time.time()
        tool_calls_made: List[Dict[str, Any]] = []
        tool_results: List[Dict[str, Any]] = []
        
        trace: List[Dict[str, Any]] = []
        
        # Obtener métricas (inyectadas o singleton global)
        if self._metrics_service is None:
            from ..services.metrics import metrics_service as default_metrics_service
            metrics_service = default_metrics_service
        else:
            metrics_service = self._metrics_service
        
        try:
            # Step 1: Retrieve RAG context
            logger.info(f"Step 1: Retrieving RAG context for: '{query[:50]}...'")
            if log_callback:
                    log_callback("agent_rag_started", {
                        "query_preview": query[:100],
                        "top_k": top_k,
                        "step": "RAG Context Retrieval",
                        "description": "Buscando información relevante en la base de datos vectorial usando embeddings semánticos",
                        "agent_type": "Orchestrator Agent"
                    })
            
            rag_start = time.time()
            rag_context = await self._get_rag_context(query, top_k)
            rag_duration = (time.time() - rag_start) * 1000
            metrics_service.record_rag_retrieval(rag_duration)
            
            if log_callback:
                log_callback("agent_rag_completed", {
                    "chunks_found": len(rag_context),
                    "chunk_ids": [c.get("chunk_id") for c in rag_context[:5]],  # Primeros 5
                    "duration_ms": round(rag_duration, 2),
                    "sources": list(set([c.get("source", "unknown") for c in rag_context])),
                    "step": "RAG Context Retrieved",
                    "description": f"Encontrados {len(rag_context)} fragmentos relevantes de {len(set([c.get('source', 'unknown') for c in rag_context]))} fuentes diferentes",
                    "technology": "Supabase pgvector + Semantic Search",
                    "agent_type": "Orchestrator Agent"
                })
            
            trace.append({
                "step": "rag_context",
                "chunks": [c.get("chunk_id") for c in rag_context],
                "count": len(rag_context)
            })
            
            # Step 2: Build initial messages with system prompt and chat history
            messages = self._build_initial_messages(query, rag_context, chat_history)
            trace.append({"step": "build_messages", "message_count": len(messages)})
            
            # Step 3: Agent reasoning loop
            iteration = 0
            final_response = None
            
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"Agent iteration {iteration}/{max_iterations}")
                
                if log_callback:
                    log_callback("agent_iteration_started", {
                        "iteration": iteration,
                        "max_iterations": max_iterations,
                        "step": f"Iteration {iteration}/{max_iterations}",
                        "description": f"El agente está analizando la consulta y planificando las acciones necesarias (iteración {iteration} de {max_iterations})",
                        "context_available": len(messages),
                        "rag_chunks_loaded": len(rag_context) if rag_context else 0,
                        "agent_type": "Orchestrator Agent"
                    })
                
                trace.append({"step": "iteration_start", "iteration": iteration})
                
                # Call LLM with tools
                # Detectar intención desde la query original
                intent = detect_intent(query)
                agent_type_map = {
                    Intent.CALENDAR: "Calendar Agent",
                    Intent.EMAIL: "Email Agent",
                    Intent.SCHEDULING: "Scheduling Agent",
                    Intent.COMMS: "Comms Agent",
                    Intent.GENERAL: "General Agent",
                }
                agent_type = agent_type_map.get(intent, "General Agent")
                
                # Filtrar herramientas según el tipo de agente
                filtered_tools = get_tools_for_agent(agent_type)
                
                if log_callback:
                    # Obtener lista de tools disponibles (filtradas)
                    available_tools = []
                    for tool_def in filtered_tools:
                        tool_name = tool_def.get("function", {}).get("name", "")
                        tool_desc = tool_def.get("function", {}).get("description", "")
                        available_tools.append({
                            "name": tool_name,
                            "description": tool_desc[:100]  # Primeros 100 caracteres
                        })
                    
                    log_callback("agent_tools_available", {
                        "iteration": iteration,
                        "step": "Available Tools",
                        "description": f"El agente tiene {len(available_tools)} herramientas disponibles para elegir",
                        "tools": available_tools,
                        "tool_count": len(available_tools),
                        "agent_type": agent_type
                    })
                    
                    log_callback("agent_llm_calling", {
                        "iteration": iteration,
                        "message_count": len(messages),
                        "step": "LLM Reasoning",
                        "agent_type": agent_type,
                        "description": f"El {agent_type} está analizando la consulta y decidiendo qué herramienta usar (si es necesario)",
                        "provider": settings.ai_provider if hasattr(settings, 'ai_provider') else "Nebius",
                        "model": settings.nebius_chat_model if hasattr(settings, 'nebius_chat_model') else "Unknown",
                        "available_tools_count": len(available_tools)
                    })
                
                llm_start = time.time()
                # Usar herramientas filtradas para este agente
                response = await self._call_llm_with_tools(messages, tools=filtered_tools)
                llm_duration = (time.time() - llm_start) * 1000
                metrics_service.record_llm_call(llm_duration)
                
                has_tool_calls = bool(response.get('tool_calls'))
                content_preview = (response.get('content') or "")[:200]
                full_content = response.get('content') or ""
                
                if log_callback:
                    reasoning = "El modelo ha generado una respuesta directa"
                    if has_tool_calls:
                        reasoning = "El modelo ha decidido que necesita usar herramientas para completar la tarea"
                    
                    # Mostrar el razonamiento completo del LLM (puede incluir pensamiento antes de decidir usar tools)
                    log_callback("agent_llm_reasoning", {
                        "iteration": iteration,
                        "step": "LLM Reasoning Output",
                        "description": "Razonamiento interno del modelo de lenguaje",
                        "reasoning_text": full_content[:500] if full_content else "Sin razonamiento visible",
                        "has_tool_calls": has_tool_calls,
                        "agent_type": agent_type
                    })
                    
                    log_callback("agent_llm_response", {
                        "iteration": iteration,
                        "has_tool_calls": has_tool_calls,
                        "content_preview": content_preview,
                        "duration_ms": round(llm_duration, 2),
                        "step": "LLM Decision",
                        "reasoning": reasoning,
                        "description": reasoning + f" (tiempo de procesamiento: {round(llm_duration, 2)}ms)",
                        "agent_type": agent_type
                    })
                
                trace.append({
                    "step": "llm_response",
                    "iteration": iteration,
                    "has_tool_calls": has_tool_calls,
                    "content_preview": content_preview
                })
                
                # Check if model wants to call tools
                if response.get('tool_calls'):
                    tool_calls_list = response.get('tool_calls', [])
                    tool_names = [tc.get('function', {}).get('name', '') for tc in tool_calls_list]
                    mcp_tools = [tn for tn in tool_names if '.' in tn]
                    
                    if log_callback:
                        # Explicar por qué se eligió cada tool
                        tool_selection_reasoning = []
                        for tool_name in tool_names:
                            tool_def = next((t for t in TOOL_DEFINITIONS if t.get("function", {}).get("name") == tool_name), None)
                            tool_desc = tool_def.get("function", {}).get("description", "Sin descripción") if tool_def else "Herramienta no encontrada"
                            tool_selection_reasoning.append({
                                "tool": tool_name,
                                "reason": tool_desc[:150]  # Primeros 150 caracteres de la descripción
                            })
                        
                        log_callback("agent_tools_detected", {
                            "iteration": iteration,
                            "tool_count": len(tool_calls_list),
                            "step": "Tool Selection Decision",
                            "description": f"El agente ha decidido usar {len(tool_calls_list)} herramienta(s) para completar la tarea",
                            "tools": tool_names,
                            "tool_selection_reasoning": tool_selection_reasoning,
                            "mcp_tools": mcp_tools,
                            "uses_mcp": len(mcp_tools) > 0,
                            "protocol": "MCP (Model Context Protocol)" if mcp_tools else "Local Registry",
                            "agent_type": agent_type
                        })
                    
                    # Execute each tool call
                    for tool_call in response['tool_calls']:
                        tool_name = tool_call['function']['name']
                        tool_args = json.loads(tool_call['function']['arguments'])
                        
                        logger.info(f"Executing tool: {tool_name}")
                        
                        if log_callback:
                            # Determinar si es MCP o local
                            tool_type = "Local Tool"
                            if "." in tool_name:
                                parts = tool_name.split(".")
                                if len(parts) == 2:
                                    tool_type = f"MCP Tool ({parts[0]})"
                            
                            log_callback("agent_tool_executing", {
                                "iteration": iteration,
                                "tool_name": tool_name,
                                "args_preview": str(tool_args)[:200],
                                "step": "Tool Execution",
                                "tool_type": tool_type,
                                "description": f"Ejecutando {tool_type}: {tool_name}",
                                "protocol": "MCP (Model Context Protocol)" if "." in tool_name else "Local Registry",
                                "arguments": {k: str(v)[:100] for k, v in tool_args.items()},
                                "agent_type": agent_type
                            })
                        
                        tool_calls_made.append({
                            "tool_name": tool_name,
                            "arguments": tool_args,
                            "call_id": tool_call['id']
                        })
                        trace.append({
                            "step": "tool_call",
                            "iteration": iteration,
                            "tool_name": tool_name,
                            "args": tool_args
                        })
                        
                        # Execute the tool via registry
                        tool_start = time.time()
                        result = await execute_tool(tool_name, **tool_args)
                        tool_duration = (time.time() - tool_start) * 1000
                        
                        if log_callback:
                            is_mcp_tool = "." in tool_name
                            log_callback("agent_tool_completed", {
                                "iteration": iteration,
                                "tool_name": tool_name,
                                "success": result.get("success", False),
                                "duration_ms": round(tool_duration, 2),
                                "result_preview": str(result.get("result", ""))[:200] if result.get("result") else None,
                                "error": result.get("error") if not result.get("success") else None,
                                "step": "Tool Execution Completed",
                                "description": f"Herramienta {'MCP' if is_mcp_tool else 'local'} completada: {tool_name}",
                                "tool_type": "MCP Tool" if is_mcp_tool else "Local Tool"
                            })
                        metrics_service.record_tool_call(
                            tool_name,
                            tool_duration,
                            result.get("success", False),
                            result.get("error"),
                        )
                        tool_results.append({
                            "call_id": tool_call['id'],
                            "tool_name": tool_name,
                            **result
                        })
                        trace.append({
                            "step": "tool_result",
                            "iteration": iteration,
                            "tool_name": tool_name,
                            "success": result.get("success", False)
                        })
                        
                        # Add assistant message with tool call
                        # Include 'type' field required by OpenAI API
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": tool_call['id'],
                                "type": "function",
                                "function": tool_call['function']
                            }]
                        })
                        
                        # Add tool result message
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call['id'],
                            "content": json.dumps(result)
                        })
                else:
                    # No more tool calls - we have the final response
                    final_response = response.get('content', '')
                    
                    if log_callback:
                        log_callback("agent_final_response", {
                            "iteration": iteration,
                            "response_preview": (final_response or "")[:300],
                            "agent_type": agent_type
                        })
                    
                    trace.append({
                        "step": "final_response",
                        "iteration": iteration,
                        "content_preview": (final_response or "")[:200]
                    })
                    break
            
            # Step 4: Limpiar trazas de <think> y extraer citas
            original_response = final_response or "I processed your request."
            
            # Si hay tool_results con texto formateado, intentar usarlo primero
            tool_text = None
            for tool_result in tool_results:
                result_data = tool_result.get("result", "")
                
                # Si el resultado es un dict, buscar campo "text" primero
                if isinstance(result_data, dict):
                    tool_text = result_data.get("text") or result_data.get("summary")
                    if tool_text and isinstance(tool_text, str) and len(tool_text) > 50:
                        logger.info(f"✅ Encontrado texto del tool en campo 'text': {len(tool_text)} chars")
                        break
                elif isinstance(result_data, str):
                    # Si el resultado es un string, podría ser el texto formateado
                    if "Próximas citas" in result_data or "eventos" in result_data.lower() or len(result_data) > 50:
                        tool_text = result_data
                        logger.info(f"✅ Encontrado texto del tool como string: {len(tool_text)} chars")
                        break
            
            # Si encontramos texto del tool, usarlo como base y solo limpiar razonamiento adicional
            if tool_text and len(tool_text) > 50:
                # El tool ya proporcionó un texto formateado, usarlo como base
                clean_text = tool_text
                logger.info(f"✅ Usando texto del tool result ({len(clean_text)} chars)")
            else:
                # Usar la respuesta del LLM y limpiarla
                if log_callback:
                    log_callback("agent_cleaning_response", {
                        "original_length": len(original_response),
                        "has_think_tags": "<think>" in original_response or "<think>" in original_response.lower(),
                        "step": "Response Cleaning",
                        "description": "Limpiando tags técnicos y extrayendo citas de las fuentes consultadas",
                        "agent_type": "Orchestrator Agent"
                    })
                
                # Limpiar tags de razonamiento
                clean_text = self._strip_think(original_response)
            
            # Extraer citas
            citations = self._extract_citations(clean_text, rag_context)
            
            # Humanizar la respuesta ANTES de enviarla
            # Pasar también tool_results para extraer nombres de eventos
            clean_text = self._humanize_response(clean_text, tool_calls_made, citations, tool_results)
            
            # Log de respuesta humanizada
            if log_callback:
                log_callback("agent_response_humanized", {
                    "original_length": len(original_response),
                    "cleaned_length": len(clean_text),
                    "step": "Response Humanized",
                    "description": f"Respuesta limpiada y humanizada: {len(original_response)} → {len(clean_text)} caracteres",
                    "agent_type": "Orchestrator Agent"
                })
            
            if log_callback:
                log_callback("agent_response_ready", {
                    "text": clean_text,  # Incluir el texto final humanizado
                    "final_length": len(clean_text),
                    "citations_count": len(citations),
                    "tools_used": [t['tool_name'] for t in tool_calls_made],
                    "step": "Response Ready",
                    "description": f"Respuesta final lista: {len(clean_text)} caracteres, {len(citations)} citas, {len(tool_calls_made)} herramientas usadas",
                    "multi_agent": len(set([t.get('tool_name', '').split('.')[0] for t in tool_calls_made if '.' in t.get('tool_name', '')])) > 1 if tool_calls_made else False,
                    "agent_type": "Orchestrator Agent"
                })
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            metrics_service.record_request(success=True)
            
            return {
                "text": clean_text,
                "tool_calls": tool_calls_made,
                "tool_results": tool_results,
                "citations": citations,
                "debug": {
                    "rag_context_used": len(rag_context) > 0,
                    "rag_chunk_ids": [c['chunk_id'] for c in rag_context],
                    "tools_called": [t['tool_name'] for t in tool_calls_made],
                    "iterations": iteration,
                    "latency_ms": elapsed_ms,
                    "trace": trace
                }
            }
            
        except Exception as e:
            logger.error(f"Agent processing failed: {e}", exc_info=True)
            elapsed_ms = int((time.time() - start_time) * 1000)
            metrics_service.record_request(success=False)
            err_msg = str(e) or repr(e)
            return {
                "text": f"I encountered an error processing your request: {err_msg}",
                "tool_calls": tool_calls_made,
                "tool_results": tool_results,
                "citations": [],
                "debug": {
                    "rag_context_used": False,
                    "rag_chunk_ids": [],
                    "tools_called": [t['tool_name'] for t in tool_calls_made],
                    "iterations": 0,
                    "error": err_msg,
                    "latency_ms": elapsed_ms,
                    "trace": trace
                }
            }
    
    async def _get_rag_context(
        self, 
        query: str, 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context from RAG.
        
        Args:
            query: User query to search for
            top_k: Number of chunks to retrieve
            
        Returns:
            List of context blocks with chunk_id, text, source, similarity
        """
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.embed_query(query)
            
            # Vector similarity search
            search_results = await db.vector_search(query_embedding, top_k)
            
            # Deduplicate by chunk_id prefix (MMR-lite)
            seen_prefixes = set()
            context_blocks = []
            
            for result in search_results:
                chunk_id = result.get('chunk_id', '')
                # Extract base ID (before #) for deduplication
                base_id = chunk_id.split('#')[0] if '#' in chunk_id else chunk_id
                
                if base_id not in seen_prefixes:
                    context_blocks.append(result)
                    seen_prefixes.add(base_id)
                
                # Limit context to avoid token overflow
                if len(context_blocks) >= 4:
                    break
            
            logger.info(f"Retrieved {len(context_blocks)} RAG context blocks")
            return context_blocks
            
        except Exception as e:
            logger.error(f"Failed to retrieve RAG context: {e}")
            return []
    
    def _build_initial_messages(
        self, 
        query: str, 
        rag_context: List[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Build the initial message list with system prompt, chat history, and RAG context.
        
        Args:
            query: User's query
            rag_context: Retrieved RAG context blocks
            chat_history: Optional previous conversation messages
            
        Returns:
            List of messages for the LLM
        """
        # Build context string with citations
        context_parts = []
        for block in rag_context:
            chunk_id = block.get('chunk_id', 'unknown')
            text = block.get('text', '')
            context_parts.append(f"[{chunk_id}] {text}")
        
        context_str = "\n\n".join(context_parts) if context_parts else "No relevant context found in knowledge base."
        
        # Get current date for accurate scheduling
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_year = datetime.now().year
        
        # System prompt that enables both RAG and tool use
        system_prompt = f"""You are an intelligent AI assistant with access to both a knowledge base and action tools.

## IMPORTANT: Current Date Information
Today's date is: {current_date}
Current year is: {current_year}
When scheduling events, ALWAYS use the current year ({current_year}) or future dates. Never use past dates.

## Your Capabilities:

1. **Knowledge Base (RAG)**: You have access to retrieved context from our database. Use it to answer questions about policies, procedures, scheduling rules, and other information.

2. **Tools**: You can take real actions:
   - `create_calendar_event`: Schedule meetings on Google Calendar
   - `list_agenda_events`: List upcoming events from your agenda
   - `confirm_agenda_event`: Confirm a proposed event
   - `search_emails`: Search for emails via IMAP (use when user asks to search, find, or read emails)
   - `read_email`: Read a specific email by ID
   - `send_email`: Send emails via Gmail
   - `send_whatsapp`: Send WhatsApp messages
   - `list_calendly_events`: List Calendly events
   - `create_calendly_event`: Create a Calendly event

## Retrieved Context from Knowledge Base:
{context_str}

## Instructions:

1. **For informational questions** (about policies, returns, shipping, scheduling rules, etc.):
   - Answer using the retrieved context above
   - Include citations in format [chunk_id] when referencing information
   - If context doesn't contain relevant info, say so

2. **For action requests**:
   - **Email requests** (search, find, read emails): Use `search_emails` or `read_email` tools
   - **Calendar requests** (schedule, list, confirm events): Use `create_calendar_event`, `list_agenda_events`, or `confirm_agenda_event`
   - **Sending messages**: Use `send_email` or `send_whatsapp`
   - If RAG context contains relevant info (e.g., default meeting duration), USE IT
   - If missing required info (date, time, email), ASK the user
   - ALWAYS use the current year ({current_year}) for dates

3. **After executing a tool**:
   - Confirm the action with relevant details
   - Include any important information (event link, meeting time, etc.)

## Important Guidelines:
- Always check if RAG context is relevant before using it
- Include citations [chunk_id] when referencing knowledge base information
- For scheduling: Check context for default durations (e.g., "standard consultation = 30 minutes")
- Be concise, professional, and helpful
- Corporate email for sending: {settings.google_calendar_email}"""

        # Build messages list starting with system prompt
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add chat history if provided (for multi-turn conversations)
        if chat_history:
            for msg in chat_history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Add current user query
        messages.append({"role": "user", "content": query})
        
        return messages
    
    async def _call_llm_with_tools(
        self, 
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Call the LLM with tool definitions.
        
        Args:
            messages: Conversation messages
            tools: Optional filtered list of tools (defaults to all tools)
            
        Returns:
            Dict with 'content' and optional 'tool_calls'
        """
        tools_to_use = tools if tools is not None else TOOL_DEFINITIONS
        if self.provider == "openai":
            return await self._call_openai(messages, tools=tools_to_use)
        elif self.provider == "anthropic":
            return await self._call_anthropic(messages, tools=tools_to_use)
        elif self.provider == "nebius":
            return await self._call_nebius(messages, tools=tools_to_use)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    async def _call_openai(
        self, 
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Call OpenAI API with tool definitions.
        
        Args:
            messages: Conversation messages
            tools: Optional filtered list of tools
            
        Returns:
            Dict with 'content' and optional 'tool_calls'
        """
        tools_to_use = tools if tools is not None else TOOL_DEFINITIONS
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools_to_use,
            tool_choice="auto",
            temperature=settings.temperature,
            max_tokens=500
        )
        
        message = response.choices[0].message
        
        return {
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in (message.tool_calls or [])
            ] if message.tool_calls else None
        }
    
    async def _call_anthropic(
        self, 
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Call Anthropic API with tool definitions.
        
        Args:
            messages: Conversation messages
            tools: Optional filtered list of tools
            
        Returns:
            Dict with 'content' and optional 'tool_calls'
        """
        tools_to_use = tools if tools is not None else TOOL_DEFINITIONS
        # Extract system message
        system_content = ""
        user_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                user_messages.append(msg)
        
        # Convert tool definitions to Anthropic format
        anthropic_tools = [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"]["parameters"]
            }
            for t in tools_to_use
        ]
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            temperature=settings.temperature,
            system=system_content,
            messages=user_messages,
            tools=anthropic_tools
        )
        
        # Parse Anthropic response format
        tool_calls = []
        content = ""
        
        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input)
                    }
                })
        
        return {
            "content": content,
            "tool_calls": tool_calls if tool_calls else None
        }

    async def _call_nebius(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Call Nebius chat completions (OpenAI-like HTTP).
        
        Args:
            messages: Conversation messages
            tools: Optional filtered list of tools
        """
        tools_to_use = tools if tools is not None else TOOL_DEFINITIONS
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools_to_use,
            "tool_choice": "auto",
            "temperature": settings.temperature,
            "max_tokens": 1500,
        }
        # trust_env=False para evitar proxys del entorno que nos devolvían 404 desde Nebius
        # Timeout aumentado a 120s para modelos grandes que pueden tardar más
        async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            try:
                resp.raise_for_status()
            except Exception:
                logger.error("Nebius chat error %s: %s", resp.status_code, resp.text)
                raise
            data = resp.json()

        msg = data.get("choices", [{}])[0].get("message", {})
        tool_calls_raw = msg.get("tool_calls") or []
        tool_calls = [
            {
                "id": tc.get("id"),
                "function": {
                    "name": tc.get("function", {}).get("name"),
                    "arguments": tc.get("function", {}).get("arguments"),
                },
            }
            for tc in tool_calls_raw
        ] if tool_calls_raw else None

        return {
            "content": msg.get("content", ""),
            "tool_calls": tool_calls,
        }
    
    def _humanize_response(self, text: str, tool_calls: List[Dict[str, Any]], citations: List[str], tool_results: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        Humaniza la respuesta del agente para que sea más natural y comprensible.
        Extrae nombres de eventos de los tool_results para nombrarlos correctamente.
        Convierte formato técnico de list_agenda_events en texto conversacional natural para voz.
        """
        if not text:
            return text
        
        # Si el texto viene del formato técnico de list_agenda_events, convertirlo a texto conversacional
        if "Próximas citas importantes:" in text or ("id=" in text and "|" in text and "estado:" in text):
            # Formatear eventos de agenda de manera conversacional
            return self._format_agenda_text(text, tool_results)
        
        # Extraer nombres de eventos de tool_results si están disponibles
        event_names = {}
        event_id_to_name = {}
        
        if tool_results:
            for result in tool_results:
                result_data = result.get("result", "")
                if isinstance(result_data, str):
                    # Intentar parsear JSON si es string
                    try:
                        result_data = json.loads(result_data)
                    except:
                        pass
                
                if isinstance(result_data, dict):
                    # Buscar eventos en el resultado
                    if "events" in result_data:
                        events = result_data["events"]
                        if isinstance(events, list):
                            for event in events:
                                if isinstance(event, dict):
                                    event_id = event.get("id") or event.get("event_id")
                                    event_title = event.get("title") or event.get("name") or event.get("event_title")
                                    if event_id and event_title:
                                        event_id_to_name[str(event_id)] = event_title
                                        event_names[event_title] = event_title
                    # También buscar directamente en el resultado
                    if "title" in result_data:
                        event_names[result_data["title"]] = result_data["title"]
                    if "name" in result_data:
                        event_names[result_data["name"]] = result_data["name"]
        
        # También buscar en tool_calls
        for tool_call in tool_calls:
            tool_name = tool_call.get("tool_name", "")
            tool_args = tool_call.get("arguments", {})
            
            # Si es list_agenda_events o list_cal_events, buscar eventos en los argumentos
            if "list" in tool_name.lower() and "event" in tool_name.lower():
                if "title" in tool_args:
                    event_names[tool_args.get("title", "")] = tool_args.get("title", "")
                if "event_title" in tool_args:
                    event_names[tool_args.get("event_title", "")] = tool_args.get("event_title", "")
        
        # Remover referencias técnicas a tools y pasos
        text = re.sub(r'Steps:\s*\d+\.\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r'Step\s+\d+:\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'The tool returned:', 'He encontrado:', text, flags=re.IGNORECASE)
        text = re.sub(r'Tool execution result:', 'Resultado:', text, flags=re.IGNORECASE)
        text = re.sub(r'text summary:', 'resumen:', text, flags=re.IGNORECASE)
        text = re.sub(r'but we also have', 'también tenemos', text, flags=re.IGNORECASE)
        text = re.sub(r'from extracted_events', 'de eventos propuestos', text, flags=re.IGNORECASE)
        text = re.sub(r'from calendar_events', 'de tu calendario', text, flags=re.IGNORECASE)
        text = re.sub(r'proposed events', 'eventos propuestos', text, flags=re.IGNORECASE)
        text = re.sub(r'calendar events', 'eventos del calendario', text, flags=re.IGNORECASE)
        
        # Mejorar nombres de eventos: buscar patrones como "event with title X" o "event titled X"
        # y reemplazarlos con el nombre real del evento
        text = re.sub(r'event\s+with\s+title\s+"([^"]+)"', r'evento "\1"', text, flags=re.IGNORECASE)
        text = re.sub(r'event\s+titled\s+"([^"]+)"', r'evento "\1"', text, flags=re.IGNORECASE)
        text = re.sub(r'event:\s*"([^"]+)"', r'evento "\1"', text, flags=re.IGNORECASE)
        
        # Buscar y mejorar referencias a eventos por ID - usar el mapeo de IDs a nombres
        def replace_event_id(match):
            event_id = match.group(1)
            # Buscar en el mapeo de IDs a nombres
            if event_id in event_id_to_name:
                return f'evento "{event_id_to_name[event_id]}"'
            # Buscar en tool_calls si hay información del evento
            for tool_call in tool_calls:
                tool_args = tool_call.get("arguments", {})
                if str(event_id) in str(tool_args.get("event_id", "")):
                    title = tool_args.get("title") or tool_args.get("event_title") or tool_args.get("name")
                    if title:
                        return f'evento "{title}"'
            return f'evento {event_id}'
        
        text = re.sub(r'event\s+ID\s+(\d+)', replace_event_id, text, flags=re.IGNORECASE)
        text = re.sub(r'ID\s+(\d+)', replace_event_id, text, flags=re.IGNORECASE)
        
        # Remover patrones técnicos comunes
        text = re.sub(r'^\d+\.\s*', '', text, flags=re.MULTILINE)  # Números al inicio de línea
        text = re.sub(r'^\s*-\s*', '• ', text, flags=re.MULTILINE)  # Listas con guiones
        
        # Convertir IDs técnicos en descripciones más naturales (solo si no se pudo extraer el nombre)
        text = re.sub(r'with IDs (\d+(?:,\s*\d+)*)', r'(\1)', text, flags=re.IGNORECASE)
        
        # Traducir frases comunes en inglés a español más natural
        text = re.sub(r'Here are', 'Aquí tienes', text, flags=re.IGNORECASE)
        text = re.sub(r'I found', 'He encontrado', text, flags=re.IGNORECASE)
        text = re.sub(r'You have', 'Tienes', text, flags=re.IGNORECASE)
        text = re.sub(r'There are', 'Hay', text, flags=re.IGNORECASE)
        text = re.sub(r'Note:', 'Nota:', text, flags=re.IGNORECASE)
        
        # Limpiar múltiples espacios y saltos de línea
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Múltiples saltos de línea
        text = re.sub(r' +', ' ', text)  # Múltiples espacios
        
        # Mejorar formato de fechas
        date_pattern = r'(\d{4}-\d{2}-\d{2})'
        def format_date_match(m):
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(m.group(1).replace('Z', '+00:00'))
                months = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                         'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
                return f"{dt.day} de {months[dt.month-1]} de {dt.year}"
            except:
                return m.group(1)
        text = re.sub(date_pattern, format_date_match, text)
        
        # Asegurar que empiece con mayúscula y termine con punto si no tiene puntuación
        text = text.strip()
        if text and not text[0].isupper():
            text = text[0].upper() + text[1:]
        if text and text[-1] not in '.!?':
            text = text + '.'
        
        return text

    def _format_agenda_text(self, text: str, tool_results: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        Formatea texto de eventos de agenda en formato conversacional natural.
        """
        if not text:
            return text
        
        # Extraer eventos de tool_results si están disponibles
        events = []
        if tool_results:
            for result in tool_results:
                result_data = result.get("result", "")
                if isinstance(result_data, str):
                    try:
                        result_data = json.loads(result_data)
                    except:
                        pass
                
                if isinstance(result_data, dict):
                    # Buscar eventos en extracted_events o calendar_events
                    for key in ["extracted_events", "calendar_events", "events"]:
                        if key in result_data:
                            events_list = result_data[key]
                            if isinstance(events_list, list):
                                events.extend(events_list)
        
        # Si tenemos eventos, formatearlos de manera natural
        if events:
            lines = ["Próximas citas:"]
            for event in events[:10]:  # Limitar a 10 eventos
                title = event.get("title") or event.get("name") or "Evento sin título"
                start = event.get("start_at") or event.get("start")
                status = event.get("status", "")
                
                # Formatear fecha
                date_str = ""
                if start:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        months = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                                 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
                        date_str = f"{dt.day} de {months[dt.month-1]} a las {dt.hour:02d}:{dt.minute:02d}"
                    except:
                        date_str = start
                
                status_text = " (confirmado)" if status == "confirmed" else " (propuesto)" if status == "proposed" else ""
                lines.append(f"• {title}{status_text}" + (f" - {date_str}" if date_str else ""))
            
            return "\n".join(lines)
        
        # Si no hay eventos en tool_results, intentar parsear el texto directamente
        # Simplificar formato técnico
        text = re.sub(r'id=(\d+)', r'evento \1', text)
        text = re.sub(r'\|\s*', ' - ', text)
        text = re.sub(r'estado:\s*(\w+)', r'(\1)', text)
        
        return text

    def _strip_think(self, text: str) -> str:
        """
        Elimina bloques <think> ... </think> o <think> ... </think>
        y todo el razonamiento interno del LLM, dejando solo la respuesta final al usuario.
        """
        if not text:
            return text
        import re
        
        # Primero intentar eliminar bloques completos con cierre (ambos formatos)
        cleaned = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.S | re.IGNORECASE)
        cleaned = re.sub(r"<think>.*?</think>\s*", "", cleaned, flags=re.S | re.IGNORECASE)
        
        # Si todavía hay tags sin cierre, eliminar desde el tag hasta el final del bloque
        if "<think>" in cleaned.lower() or "<think>" in cleaned.lower():
            # Eliminar cualquier tag y todo lo que sigue hasta encontrar contenido real
            patterns = [
                r"<think>.*?(?:</think>|$)",
                r"<think>.*?(?:</think>|$)",
            ]
            for pattern in patterns:
                cleaned = re.sub(pattern, "", cleaned, flags=re.S | re.IGNORECASE)
        
        # Eliminar frases comunes de razonamiento interno que no tienen tags
        # PERO ser más conservador para no eliminar respuestas válidas
        reasoning_patterns = [
            r"^We note that.*?\n",
            r"^Let's process.*?\n",
            r"^We are given.*?\n",
            r"^The response includes.*?\n",
            r"^Actually,.*?\n",
            r"^However,.*?\n",
            r"^But Nota:.*?\n",
            r"^Nota:.*?\n",
            r"^We should.*?\n",
            r"^We'll.*?\n",
            r"^We can.*?\n",
            r"^This might be.*?\n",
            r"^How should we.*?\n",
            r"^Therefore,.*?\n",
            r"^Alternatively,.*?\n",
            r"^Since the user.*?\n",
        ]
        for pattern in reasoning_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
        
        # Si después de limpiar el texto está muy corto o vacío, intentar extraer la parte útil
        if len(cleaned.strip()) < 50 and len(text) > 100:
            # Buscar frases que parecen respuestas reales (empiezan con mayúscula, tienen puntuación)
            sentences = re.findall(r'[A-ZÁÉÍÓÚ][^.!?]*[.!?]', cleaned)
            if sentences:
                # Tomar las últimas 2-3 frases que parecen respuestas
                cleaned = ' '.join(sentences[-3:])
        
        # Buscar y extraer solo la parte final que parece una respuesta real
        # Buscar frases que empiezan con mayúscula y parecen respuestas directas
        # Eliminar todo lo que parece razonamiento (frases que empiezan con "We", "Let's", "Since", etc.)
        lines = cleaned.split('\n')
        response_lines = []
        skip_reasoning = True
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # Si encontramos una línea que parece una respuesta real, empezar a incluir
            if re.match(r'^[A-ZÁÉÍÓÚ][^:]*[.!?]$', line_stripped) or \
               re.match(r'^[📅🎯✅❌•\-]', line_stripped) or \
               line_stripped.startswith('Próximas') or \
               line_stripped.startswith('Encontré') or \
               line_stripped.startswith('Tienes') or \
               line_stripped.startswith('Aquí'):
                skip_reasoning = False
                response_lines.append(line)
            elif not skip_reasoning:
                # Si ya estamos en modo respuesta, incluir la línea
                response_lines.append(line)
            elif not any(line_stripped.lower().startswith(prefix) for prefix in 
                        ['we ', 'let\'s', 'since', 'actually', 'however', 'but nota', 'nota:', 
                         'this might', 'how should', 'therefore', 'alternatively', 'we\'ll', 'we can']):
                # Si no es razonamiento obvio, incluirla
                response_lines.append(line)
        
        cleaned = '\n'.join(response_lines)
        
        # Si después de todo esto todavía hay mucho texto de razonamiento, buscar el último párrafo que parece respuesta
        if len(cleaned) > 1000 and 'id=' in cleaned:
            # Parece que todavía hay razonamiento, buscar la última parte que parece respuesta
            # Buscar patrones como "Próximas citas" o listas de eventos
            match = re.search(r'(Próximas citas|Encontré|Tienes|Aquí tienes|No encontré|He encontrado|No hay|Hay \d+).*$', cleaned, flags=re.S | re.IGNORECASE)
            if match:
                cleaned = match.group(0)
        
        # Si después de todo el texto está vacío o muy corto, intentar recuperar algo del original
        if len(cleaned.strip()) < 20 and len(text) > 50:
            # Buscar cualquier frase que parezca una respuesta (no razonamiento)
            useful_patterns = [
                r'(Próximas citas|Encontré|Tienes|Aquí tienes|No encontré|He encontrado|No hay|Hay \d+|I found|You have|Here are).*$',
                r'([A-ZÁÉÍÓÚ][^.!?]{10,}[.!?])',
            ]
            for pattern in useful_patterns:
                matches = re.findall(pattern, text, flags=re.S | re.IGNORECASE | re.MULTILINE)
                if matches:
                    # Tomar las últimas 2 frases útiles
                    if isinstance(matches[0], tuple):
                        cleaned = ' '.join([m[0] if isinstance(m, tuple) else m for m in matches[-2:]])
                    else:
                        cleaned = ' '.join(matches[-2:])
                    break
        
        # Si todavía está vacío, devolver el texto original limpio de tags pero sin más procesamiento
        if len(cleaned.strip()) < 10:
            # Solo eliminar tags de razonamiento pero mantener el resto
            temp_cleaned = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.S | re.IGNORECASE)
            temp_cleaned = re.sub(r"<think>.*?</think>\s*", "", temp_cleaned, flags=re.S | re.IGNORECASE)
            # Si después de esto sigue siendo muy largo, tomar las últimas líneas que no son razonamiento
            if len(temp_cleaned) > 500:
                lines = temp_cleaned.split('\n')
                non_reasoning_lines = [l for l in lines if l.strip() and not l.strip().lower().startswith(('we ', 'let\'s', 'since', 'however', 'actually', 'but nota', 'nota:'))]
                if non_reasoning_lines:
                    cleaned = '\n'.join(non_reasoning_lines[-5:])
                else:
                    cleaned = temp_cleaned[-500:]  # Tomar últimos 500 caracteres
            else:
                cleaned = temp_cleaned
        
        # Limpiar múltiples saltos de línea y espacios al inicio
        cleaned = re.sub(r'^\s*\n+\s*', '', cleaned)
        cleaned = cleaned.strip()
        
        # Si después de todo sigue vacío, devolver un mensaje por defecto
        if not cleaned or len(cleaned.strip()) < 5:
            cleaned = "He procesado tu solicitud. ¿Hay algo más en lo que pueda ayudarte?"
        
        return cleaned
    
    def _extract_citations(
        self, 
        text: str, 
        context_blocks: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Extract citations from the response text.
        
        Args:
            text: Generated response text
            context_blocks: RAG context blocks that were provided
            
        Returns:
            List of valid chunk_ids that were cited
        """
        import re
        
        # Find all citations in format [chunk_id]
        citation_pattern = r'\[([^\]]+)\]'
        found_citations = re.findall(citation_pattern, text)
        
        # Filter to only include valid chunk_ids from context
        valid_chunk_ids = {block['chunk_id'] for block in context_blocks}
        valid_citations = [
            cite for cite in found_citations 
            if cite in valid_chunk_ids
        ]
        
        # Remove duplicates while preserving order
        unique_citations = []
        for cite in valid_citations:
            if cite not in unique_citations:
                unique_citations.append(cite)
        
        return unique_citations


# Global agent service instance
agent_service = AgentService()


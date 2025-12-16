"""
Grafo multiagente (LangGraph) con compatibilidad retro.
Si LANGGRAPH_AGENT=true y langgraph está instalado, usa el grafo; si no, delega en agent_service.
"""

import logging
import re
from typing import Dict, Any, List, Optional, TypedDict, Callable
from enum import Enum
import os
import httpx
from datetime import datetime

from .orchestrator import agent_service
from ..config.settings import get_settings
from ..services.rag import rag_service as default_rag_service
from .tool_exec import execute_tool

logger = logging.getLogger(__name__)

try:
    from langgraph.graph import StateGraph, END
except ImportError:
    StateGraph = None  # LangGraph no instalado aún
    END = "END"


class Intent(str, Enum):
    CALENDAR = "calendar"
    EMAIL = "email"
    SCHEDULING = "scheduling"
    COMMS = "comms"
    PREFERENCES = "preferences"
    GENERAL = "general"


def intent_router(query: str) -> Intent:
    """Stub de ruteo de intención."""
    q = query.lower()
    if any(k in q for k in ["calendar", "reunión", "cita", "meeting"]):
        return Intent.CALENDAR
    if any(k in q for k in ["email", "correo", "mail"]):
        return Intent.EMAIL
    if any(k in q for k in ["disponibilidad", "availability", "calendly"]):
        return Intent.SCHEDULING
    if any(k in q for k in ["whatsapp", "mensaje", "notificación"]):
        return Intent.COMMS
    if any(k in q for k in ["preferencia", "preferencias", "configuración", "ajuste"]):
        return Intent.PREFERENCES
    return Intent.GENERAL


async def rag_retriever(query: str, top_k: int, rag_service=None) -> List[Dict[str, Any]]:
    """
    Retrieval ligero para el grafo: no genera respuesta LLM, sólo contexto y citas.
    
    Args:
        query: Query del usuario
        top_k: Número de chunks a recuperar
        rag_service: Servicio RAG opcional (para inyección de dependencias)
    """
    # Usar servicio inyectado o singleton global para compatibilidad
    service = rag_service if rag_service is not None else default_rag_service
    result = await service.retrieve_context(query, top_k=top_k)
    ctx_blocks = result.get("contexts", [])
    citations = result.get("citations", [])
    # Compactamos en un solo bloque para el response_generator, pero guardamos contexto completo.
    joined_text = "\n".join([c.get("text", "") for c in ctx_blocks])
    return [{"text": joined_text, "citations": citations, "contexts": ctx_blocks}]


async def policy_checker(intent: Intent, context: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Políticas básicas:
    - Horario laboral 09:00-19:00 local: si calendar/scheduling fuera de rango, requiere confirmación.
    - Placeholder conflicto: si detectamos conflicto previo, marcar requiere confirmación (lo setea node_conflict_check).
    """
    now_h = datetime.now().hour
    business_hours = 9 <= now_h < 19
    requires_confirmation = False
    notes = []

    if intent in {Intent.CALENDAR, Intent.SCHEDULING} and not business_hours:
        requires_confirmation = True
        notes.append("Fuera de horario laboral (09-19); pide confirmación.")

    return {
        "approved": not requires_confirmation,
        "requires_confirmation": requires_confirmation,
        "notes": "; ".join(notes) if notes else "ok",
        "intent": intent.value,
    }


async def tool_executor(tool_name: str, **kwargs) -> Dict[str, Any]:
    """Proxy a tool_exec; soporta MCP/mock según config."""
    return await execute_tool(tool_name, **kwargs)


async def llm_intent_router_llm(query: str) -> Optional[Intent]:
    """
    Router con LLM (si AI_PROVIDER=nebius y hay router_model); fallback None.
    """
    settings = get_settings()
    if settings.ai_provider != "nebius":
        return None
    if not settings.nebius_router_model or not settings.nebius_api_key:
        return None
    try:
        headers = {"Authorization": f"Bearer {settings.nebius_api_key}"}
        prompt = (
            "Clasifica la intención del usuario en: calendar, email, scheduling, comms, general.\n"
            f"Usuario: {query}\n"
            "Devuelve solo una palabra de esa lista."
        )
        payload = {
            "model": settings.nebius_router_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4,
            "temperature": 0.0,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{settings.nebius_base_url.rstrip('/')}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            text = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
                .lower()
            )
        mapping = {
            "calendar": Intent.CALENDAR,
            "email": Intent.EMAIL,
            "scheduling": Intent.SCHEDULING,
            "comms": Intent.COMMS,
            "general": Intent.GENERAL,
        }
        return mapping.get(text)
    except Exception:
        return None


def _format_iso(dt_str: Optional[str]) -> Optional[str]:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_str


def _format_events(result: Dict[str, Any]) -> str:
    events = []
    for ev in result.get("extracted_events", []) or []:
        events.append(
            {
                "title": ev.get("title") or "(sin título)",
                "start": _format_iso(ev.get("start_at")),
                "end": _format_iso(ev.get("end_at")),
                "status": ev.get("status") or "",
                "source": "extracted",
            }
        )
    for ev in result.get("calendar_events", []) or []:
        events.append(
            {
                "title": ev.get("title") or "(sin título)",
                "start": _format_iso(ev.get("start_at")),
                "end": _format_iso(ev.get("end_at")),
                "status": ev.get("status") or "",
                "source": ev.get("provider") or "calendar",
            }
        )
    if not events:
        return "No encontré próximas citas en la agenda."
    lines = ["Próximas citas:"]
    for ev in sorted(events, key=lambda x: x.get("start") or ""):
        lines.append(
            f"- {ev['title']} | {ev.get('start')} - {ev.get('end')} | estado: {ev.get('status')} ({ev.get('source')})"
        )
    return "\n".join(lines)


async def response_generator(
    user_query: str,
    intent: Intent,
    rag_context: List[Dict[str, Any]],
    tool_results: List[Dict[str, Any]],
    tool_plan: List[str],
) -> str:
    # Si hay resultados de herramientas, priorizar mostrar algo útil
    for tr in tool_results or []:
        if tr.get("tool_name") == "list_agenda_events" and tr.get("success"):
            return _format_events(tr.get("result", {}))

    # Fallback RAG: usa contexts y citas si están disponibles
    if rag_context:
        block = rag_context[0]
        txt = block.get("text", "")
        cites = block.get("citations", [])
        cite_str = f"\nCitas: {cites}" if cites else ""
        return f"[intent={intent.value}] {txt}{cite_str}"

    tools_str = f" Tools: {[t.get('tool_name') for t in tool_results]}" if tool_results else ""
    plan_str = f" Plan: {tool_plan}" if tool_plan else ""
    return f"[intent={intent.value}] Sin contexto RAG.{tools_str}{plan_str}"


class AgentState(TypedDict, total=False):
    user_query: str
    intent: Intent
    agent: str
    agent_model: str
    rag_context: List[Dict[str, Any]]
    policy: Dict[str, Any]
    tool_plan: List[str]
    tool_plan_details: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    final_text: str
    citations: List[str]
    session_id: Optional[str]
    agent_note: str
    debug: List[Dict[str, Any]]
    execute_tools: bool


def build_graph():
    """
    Construye un StateGraph:
      entry -> intent -> rag -> policy -> agent -> plan -> tool -> response -> END
    """
    if StateGraph is None:
        return None

    graph = StateGraph(AgentState)

    settings_local = get_settings()

    def agent_model_for(intent: Intent) -> str:
        """Selecciona modelo por rol. Supervisor no se usa aún en grafo."""
        # Especialistas: un único modelo por ahora
        return settings_local.nebius_specialist_model or settings_local.nebius_chat_model

    def _trace(state: AgentState, step: str, info: Dict[str, Any]) -> Dict[str, Any]:
        dbg = state.get("debug", [])
        dbg = dbg + [{"step": step, **info}]
        return {"debug": dbg}

    def _extract_emails(text: str) -> List[str]:
        return re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)

    def _truncate(txt: str, limit: int = 120) -> str:
        return txt if len(txt) <= limit else txt[: limit - 3] + "..."

    def _trace(state: AgentState, step: str, info: Dict[str, Any]) -> Dict[str, Any]:
        dbg = state.get("debug", [])
        dbg = dbg + [{"step": step, **info}]
        return {"debug": dbg}

    async def node_intent(state: AgentState) -> Dict[str, Any]:
        # Primero: router LLM Nebius si está disponible
        llm_int = await llm_intent_router_llm(state["user_query"])
        intent_value = llm_int or intent_router(state["user_query"])
        agent_map = {
            Intent.CALENDAR: "CalendarAgent",
            Intent.EMAIL: "EmailAgent",
            Intent.SCHEDULING: "SchedulingAgent",
            Intent.COMMS: "CommsAgent",
            Intent.PREFERENCES: "PersonalPreferenceAgent",
            Intent.GENERAL: "GeneralAgent",
        }
        agent_name = agent_map.get(intent_value, "GeneralAgent")
        logger.info("[intent] %s -> %s", state["user_query"], intent_value.value)
        return {
            "intent": intent_value,
            "agent": agent_name,
            "agent_model": agent_model_for(intent_value),
            **_trace(state, "intent", {"intent": intent_value.value, "agent": agent_name}),
        }

    async def node_rag(state: AgentState) -> Dict[str, Any]:
        # Intentar obtener rag_service del container si está disponible
        rag_service_to_use = None
        try:
            from ..core.container import get_container
            container = get_container()
            rag_service_to_use = container.rag_service
        except Exception:
            # Fallback a singleton global
            pass
        ctx = await rag_retriever(state["user_query"], top_k=settings_local.default_top_k, rag_service=rag_service_to_use)
        logger.info("[rag] retrieved %d blocks", len(ctx))
        return {"rag_context": ctx, **_trace(state, "rag", {"ctx": len(ctx)})}

    async def node_conflict_check(state: AgentState) -> Dict[str, Any]:
        """
        Paso previo a la política: intenta detectar conflictos contra agenda ya confirmada.
        Usa list_agenda_events si execute_tools=true y hay args completos; si no, sólo marca planned.
        Regla: si hay evento confirmado solapado ±60min con mismo título aproximado, requiere confirmación.
        """
        plan = state.get("tool_plan") or []
        details = state.get("tool_plan_details") or []
        execute_flag = state.get("execute_tools", False)
        tool_calls: List[Dict[str, Any]] = state.get("tool_calls", []) or []
        tool_results: List[Dict[str, Any]] = state.get("tool_results", []) or []
        requires_confirmation = False
        note = ""

        # Solo aplicamos a calendar/scheduling
        if state.get("intent") not in {Intent.CALENDAR, Intent.SCHEDULING}:
            return {**_trace(state, "conflict_check", {"skipped": True})}

        # Intentar usar list_agenda_events si existe en plan o como extra
        has_list = any(tc.get("tool") == "list_agenda_events" for tc in details)
        if not has_list:
            details = details + [{
                "tool": "list_agenda_events",
                "args": {}
            }]

        if not execute_flag:
            tool_calls.append({"tool": "list_agenda_events", "status": "planned"})
            return {
                "tool_plan_details": details,
                "tool_calls": tool_calls,
                "tool_results": tool_results,
                **_trace(state, "conflict_check", {"planned": True})
            }

        # Ejecutar list_agenda_events si no se ha ejecutado ya
        for d in details:
            if d.get("tool") != "list_agenda_events":
                continue
            try:
                res = await tool_executor("list_agenda_events", **d.get("args", {}))
                tool_calls.append({"tool": "list_agenda_events", "status": "executed"})
                tool_results.append({
                    "tool_name": "list_agenda_events",
                    "success": res.get("success"),
                    "result": res.get("result"),
                    "error": res.get("error"),
                })
                events = (res.get("result") or {}).get("calendar_events", []) + (res.get("result") or {}).get("extracted_events", [])
                # Regla simple: conflicto si cualquier evento confirmed dentro de ±60min del start propuesto
                # NOTA: Como no tenemos start_datetime concreto aquí (placeholder), solo marcamos nota informativa
                note = "Agenda consultada; si hay solape confirmed, requerir confirmación."
            except Exception as exc:
                tool_calls.append({"tool": "list_agenda_events", "status": "error", "error": str(exc)})
                note = f"Error consultando agenda: {exc}"

        return {
            "tool_plan_details": details,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "policy": {
                "approved": not requires_confirmation,
                "requires_confirmation": requires_confirmation,
                "notes": note or "ok",
                "intent": state.get("intent").value if state.get("intent") else "",
            },
            **_trace(state, "conflict_check", {"note": note})
        }

    async def node_policy(state: AgentState) -> Dict[str, Any]:
        pol = await policy_checker(state["intent"], state.get("rag_context", []))
        logger.info("[policy] approved=%s", pol.get("approved"))
        return {"policy": pol, **_trace(state, "policy", {"approved": pol.get("approved")})}

    def _plan_calendar(state: AgentState) -> Dict[str, Any]:
        if state.get("tool_plan_details"):
            return {"plan": state["tool_plan"], "details": state["tool_plan_details"]}
        summary = _truncate(state["user_query"], 120)
        details = [{
            "tool": "create_calendar_event",
            "args": {
                "summary": summary,
                "start_datetime": "TODO_START_ISO",
                "end_datetime": "TODO_END_ISO",
                "description": "",
                "attendees": [],
                "timezone": "UTC",
                "source": "graph",
            },
        }]
        return {"plan": ["create_calendar_event"], "details": details}

    def _plan_email(state: AgentState) -> Dict[str, Any]:
        if state.get("tool_plan_details"):
            return {"plan": state["tool_plan"], "details": state["tool_plan_details"]}
        emails = _extract_emails(state["user_query"])
        to_list = emails if emails else ["TODO_EMAIL"]
        subject = _truncate(state["user_query"], 80)
        body = "Por favor confirma el contenido."
        details = [{
            "tool": "send_email",
            "args": {
                "to": to_list,
                "subject": subject,
                "body": body,
            },
        }]
        return {"plan": ["send_email"], "details": details}

    def _plan_scheduling(state: AgentState) -> Dict[str, Any]:
        # Hasta tener tools de disponibilidad, usamos create_calendar_event
        if state.get("tool_plan_details"):
            return {"plan": state["tool_plan"], "details": state["tool_plan_details"]}
        summary = _truncate(state["user_query"], 120)
        details = [{
            "tool": "create_calendar_event",
            "args": {
                "summary": summary,
                "start_datetime": "TODO_START_ISO",
                "end_datetime": "TODO_END_ISO",
                "description": "Scheduling placeholder",
                "attendees": [],
                "timezone": "UTC",
                "source": "graph",
            },
        }]
        return {"plan": ["create_calendar_event"], "details": details}

    def _plan_comms(state: AgentState) -> Dict[str, Any]:
        # Plan hacia MCP WhatsApp (mapped en mapping.json) con placeholders
        if state.get("tool_plan_details"):
            return {"plan": state["tool_plan"], "details": state["tool_plan_details"]}
        msg = _truncate(state["user_query"], 200)
        details = [{
            "tool": "send_whatsapp",
            "args": {
                "to": "TODO_PHONE",
                "message": msg,
            },
        }]
        return {"plan": ["send_whatsapp"], "details": details}

    def _plan_preferences(state: AgentState) -> Dict[str, Any]:
        # Placeholder: leer/guardar preferencias (sin tool aún)
        return {"plan": [], "details": []}

    def _plan_general(state: AgentState) -> Dict[str, Any]:
        return {"plan": state.get("tool_plan", []), "details": state.get("tool_plan_details", [])}

    def node_agent_specialist(state: AgentState) -> Dict[str, Any]:
        """
        Ajusta plan según agente especializado. No ejecuta tools, solo planifica.
        """
        intent = state.get("intent", Intent.GENERAL)
        planners = {
            Intent.CALENDAR: _plan_calendar,
            Intent.EMAIL: _plan_email,
            Intent.SCHEDULING: _plan_scheduling,
            Intent.COMMS: _plan_comms,
            Intent.PREFERENCES: _plan_preferences,
            Intent.GENERAL: _plan_general,
        }
        planner = planners.get(intent, _plan_general)
        planned_bundle = planner(state)
        planned = planned_bundle.get("plan", [])
        details = planned_bundle.get("details", [])
        note = f"Agente {intent.value}: plan {planned}" if planned else f"Agente {intent.value}: sin plan"
        logger.info("[agent] %s", note)
        return {
            "tool_plan": planned,
            "tool_plan_details": details,
            "agent_note": note,
            **_trace(state, "agent", {"plan": planned, "details": details}),
        }

    def node_plan(state: AgentState) -> Dict[str, Any]:
        intent = state.get("intent", Intent.GENERAL)
        # Planes básicos usando solo tools disponibles en registry (create_calendar_event, send_email)
        plan_map = {
            Intent.CALENDAR: ["create_calendar_event"],
            Intent.EMAIL: ["send_email"],
            Intent.SCHEDULING: ["create_calendar_event"],  # placeholder hasta tener get_availability/create_meeting
            Intent.COMMS: [],  # evitar tool inexistente (send_whatsapp no está registrado aquí)
            Intent.GENERAL: [],
        }
        plan = plan_map.get(intent, [])
        logger.info("[plan] intent=%s -> %s", intent.value if hasattr(intent, 'value') else intent, plan)
        # No sobreescribimos detalles si ya los generó el agente especializado
        if not state.get("tool_plan_details"):
            return {"tool_plan": plan, "tool_plan_details": [], **_trace(state, "plan", {"plan": plan})}
        return {"tool_plan": plan, **_trace(state, "plan", {"plan": plan, "details": state.get("tool_plan_details")})}

    async def node_tool(state: AgentState) -> Dict[str, Any]:
        """
        Ejecuta tools y, para list_agenda_events, devuelve texto directo sin re-LLM.
        """
        plan = state.get("tool_plan") or []
        details = state.get("tool_plan_details") or []
        execute_flag = state.get("execute_tools", False)
        tool_calls: List[Dict[str, Any]] = []
        tool_results: List[Dict[str, Any]] = []

        if not execute_flag:
            # Solo planificar
            if details:
                for d in details:
                    tool_calls.append(
                        {
                            "tool": d.get("tool"),
                            "status": "planned",
                            "args": d.get("args", {}),
                        }
                    )
            else:
                for tool_name in plan:
                    tool_calls.append({"tool": tool_name, "status": "planned"})
            logger.info("[tool] planned=%s (no execute)", plan)
            return {
                "tool_calls": tool_calls,
                **_trace(state, "tool", {"planned": plan, "details": details}),
            }

        # Modo ejecución real: solo ejecuta si hay args completos
        to_run = details if details else [{"tool": t, "args": {}} for t in plan]
        final_text_direct: Optional[str] = None

        for d in to_run:
            tool_name = d.get("tool")
            args = d.get("args", {}) or {}
            if not tool_name:
                continue
            # Si hay placeholders TODO_, no ejecutar
            if any(isinstance(v, str) and v.startswith("TODO") for v in args.values()):
                tool_calls.append(
                    {
                        "tool": tool_name,
                        "status": "skipped_missing_args",
                        "args": args,
                    }
                )
                continue
            try:
                logger.info("[tool] executing=%s args=%s", tool_name, list(args.keys()))
                res = await tool_executor(tool_name, **args)
                tool_calls.append({"tool": tool_name, "status": "executed", "args": args})

                if tool_name == "list_agenda_events":
                    payload = res.get("result") if isinstance(res, dict) else res
                    if payload is None:
                        payload = res
                    final_text_direct = payload.get("text") if isinstance(payload, dict) else None
                    tool_results.append({
                        "tool_name": tool_name,
                        "success": res.get("success") if isinstance(res, dict) else True,
                        "result": payload,
                        "error": res.get("error") if isinstance(res, dict) else None,
                    })
                    # Construir respuesta directa y cortar la ruta LLM
                    break

                tool_results.append({
                    "tool_name": tool_name,
                    "success": res.get("success"),
                    "result": res if res.get("result") is None else res.get("result"),
                    "error": res.get("error"),
                })
            except Exception as exc:
                logger.error("[tool] error executing %s: %s", tool_name, exc)
                tool_calls.append({"tool": tool_name, "status": "error", "args": args, "error": str(exc)})

        return {
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "final_text": final_text_direct,
            **_trace(state, "tool", {"executed": [c.get("tool") for c in tool_calls]}),
        }

    async def node_response(state: AgentState) -> Dict[str, Any]:
        # Si ya tenemos final_text directo (e.g., list_agenda_events), úsalo
        if state.get("final_text"):
            txt = state["final_text"]
        else:
            txt = await response_generator(
                state["user_query"],
                state.get("intent", Intent.GENERAL),
                state.get("rag_context", []),
                state.get("tool_results", []),
                state.get("tool_plan", []),
            )
        citations = []
        if state.get("rag_context"):
            citations = state["rag_context"][0].get("citations", [])
        logger.info("[response] done, cites=%d", len(citations))
        return {"final_text": txt, "citations": citations, **_trace(state, "response", {"cites": citations})}

    graph.add_node("intent", node_intent)
    graph.add_node("rag", node_rag)
    graph.add_node("conflict_check", node_conflict_check)
    graph.add_node("policy", node_policy)
    graph.add_node("agent", node_agent_specialist)
    graph.add_node("plan", node_plan)
    graph.add_node("tool", node_tool)
    graph.add_node("response", node_response)

    graph.set_entry_point("intent")
    graph.add_edge("intent", "rag")
    graph.add_edge("rag", "conflict_check")
    graph.add_edge("conflict_check", "policy")
    graph.add_edge("policy", "agent")
    graph.add_edge("agent", "plan")
    graph.add_edge("plan", "tool")
    graph.add_edge("tool", "response")
    graph.add_edge("response", END)

    return graph.compile()


class AgentOrchestrator:
    """
    Wrapper compatible con la interfaz actual.
    Si LANGGRAPH_AGENT=true y langgraph está instalado, usa el grafo.
    Si no, delega en agent_service (flujo actual).
    """

    def __init__(self):
        self.settings = get_settings()
        self.use_langgraph = os.getenv("LANGGRAPH_AGENT", "false").lower() == "true"
        self.graph = build_graph() if self.use_langgraph else None

    async def run(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        user_id: Optional[str] = None,
        top_k: Optional[int] = None,
        log_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        if self.use_langgraph and self.graph:
            init_state: AgentState = {
                "user_query": query,
                "rag_context": [],
                "tool_calls": [],
                "tool_results": [],
                "tool_plan": [],
                "tool_plan_details": [],
                "session_id": user_id,
                # Flag de ejecución real opcional, configurable por env
                "execute_tools": os.getenv("EXECUTE_TOOLS_IN_GRAPH", "false").lower() == "true",
            }
            result_state = await self.graph.ainvoke(init_state)
            return {
                "text": result_state.get("final_text", ""),
                "tool_calls": result_state.get("tool_calls", []),
                "tool_results": result_state.get("tool_results", []),
                "citations": result_state.get("citations", []),
                "debug": {
                    "path": "langgraph",
                    "intent": str(result_state.get("intent", "")),
                    "trace": result_state.get("debug", []),
                },
            }

        # Compatibilidad: orquestador existente
        return await agent_service.process_query(
            query=query,
            chat_history=chat_history,
            user_id=user_id,
            top_k=top_k or self.settings.default_top_k,
            max_iterations=self.settings.max_agent_iterations,
            log_callback=log_callback,
        )


# Instancia global
agent_orchestrator = AgentOrchestrator()


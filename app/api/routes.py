from fastapi import APIRouter, HTTPException
from typing import Dict
import re
import httpx
import json
import base64
from pathlib import Path

from ..config.settings import get_settings
from ..core.container import get_container
from ..schemas.requests import AgentRequest
from ..schemas.responses import AgentResponse, ToolCallInfo, ToolResultInfo, AgentDebugInfo
from ..agents.tools.agenda_tool import agenda_list_tool
from ..agents.tools.confirm_event_tool import confirm_event_tool
from ..agents.tools.list_cal_tool import list_cal_tool
from ..agents.tools.email_tool import email_tool

router = APIRouter(prefix="/api/v1", tags=["API v1"])
settings = get_settings()


@router.post("/text", response_model=AgentResponse)
async def text_entrypoint(request: AgentRequest):
    """
    Endpoint mínimo de texto → agente.
    Usa el agent_service actual; más adelante se sustituirá por LangGraph + MCP.
    """
    try:
        q_lower = request.query.lower()
        # Atajo: peticiones de agendar fuera de horario laboral (09-19) -> pedir confirmación sin pasar por LLM
        sched_keywords = ["programa", "agenda", "agendar", "reunión", "meeting", "cita"]
        if any(k in q_lower for k in sched_keywords):
            from datetime import datetime
            now_h = datetime.now().hour
            if not (9 <= now_h < 19):
                return AgentResponse(
                    text="Fuera de horario laboral (09-19). ¿Confirmo de todos modos?",
                    tool_calls=[],
                    tool_results=[],
                    citations=[],
                    debug=AgentDebugInfo(
                        rag_context_used=False,
                        rag_chunk_ids=[],
                        tools_called=[],
                        iterations=0,
                        latency_ms=0,
                    ),
                )

        # Atajo confirmación: "confirma id=123" o similar
        m = re.search(r"(confirma|confirmar|confirm|agendar)\s+(?:id\s*=?\s*)?(\d+)", q_lower)
        if m:
            ev_id = int(m.group(2))
            res = await confirm_event_tool.execute(event_id=ev_id)
            call_id = "direct-confirm-1"
            if res.get("success"):
                return AgentResponse(
                    text=f"Evento {ev_id} confirmado en Google Calendar.",
                    tool_calls=[
                        ToolCallInfo(
                            tool_name="confirm_agenda_event",
                            arguments={"event_id": ev_id},
                            call_id=call_id,
                        )
                    ],
                    tool_results=[
                        ToolResultInfo(
                            call_id=call_id,
                            tool_name="confirm_agenda_event",
                            success=True,
                            result=res["result"],
                            error=None,
                        )
                    ],
                    citations=[],
                    debug=AgentDebugInfo(
                        rag_context_used=False,
                        rag_chunk_ids=[],
                        tools_called=["confirm_agenda_event"],
                        iterations=1,
                        latency_ms=0,
                    ),
                )

        # Atajo: si la intención es agenda/citas o pedir confirmados, responde directo con la tool
        agenda_keywords = ["cita", "citas", "agenda", "appointment", "appointments", "próximas citas", "confirmados", "eventos confirmados"]
        if any(k in q_lower for k in agenda_keywords):
            # Si piden confirmados, usa list_cal_events; de lo contrario, lista agenda (supabase)
            if "confirmados" in q_lower or "eventos confirmados" in q_lower:
                res = await list_cal_tool.execute()
                if res.get("success"):
                    call_id = "direct-cal-1"
                    evs = res["result"].get("events", [])
                    lines = ["Eventos confirmados (Google Calendar):"] if evs else ["No hay eventos confirmados próximos."]
                    for ev in evs:
                        start = ev.get("start_fmt") or ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date") or ev.get("start")
                        end = ev.get("end_fmt") or ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date") or ev.get("end")
                        lines.append(f"- {ev.get('summary')} | {start} - {end}")
                    return AgentResponse(
                        text="\n".join(lines),
                        tool_calls=[
                            ToolCallInfo(
                                tool_name="list_cal_events",
                                arguments={},
                                call_id=call_id,
                            )
                        ],
                        tool_results=[
                            ToolResultInfo(
                                call_id=call_id,
                                tool_name="list_cal_events",
                                success=True,
                                result=res["result"],
                                error=None,
                            )
                        ],
                        citations=[],
                        debug=AgentDebugInfo(
                            rag_context_used=False,
                            rag_chunk_ids=[],
                            tools_called=["list_cal_events"],
                            iterations=1,
                            latency_ms=0,
                        ),
                    )
            else:
                res = await agenda_list_tool.execute(limit=request.top_k or 5)
                if res.get("success"):
                    call_id = "direct-agenda-1"
                    return AgentResponse(
                        text=res["result"].get("text", "No encontré próximas citas."),
                        tool_calls=[
                            ToolCallInfo(
                                tool_name="list_agenda_events",
                                arguments={"limit": request.top_k or 5},
                                call_id=call_id,
                            )
                        ],
                        tool_results=[
                            ToolResultInfo(
                                call_id=call_id,
                                tool_name="list_agenda_events",
                                success=True,
                                result=res["result"],
                                error=None,
                            )
                        ],
                        citations=[],
                        debug=AgentDebugInfo(
                            rag_context_used=False,
                            rag_chunk_ids=[],
                            tools_called=["list_agenda_events"],
                            iterations=1,
                            latency_ms=0,
                        ),
                    )
            # si falla, continúa al flujo normal

        chat_history = None
        if request.chat_history:
            chat_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.chat_history
            ]

        # Flujo estándar (agent_service)
        container = get_container()
        result = await container.agent_service.process_query(
            query=request.query,
            chat_history=chat_history,
            user_id=request.user_id,
            top_k=request.top_k or settings.default_top_k,
            max_iterations=settings.max_agent_iterations,
        )

        return AgentResponse(**result)
    except Exception as exc:  # pragma: no cover - capa fina de transporte
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/confirm_event", response_model=AgentResponse)
async def confirm_event(payload: Dict[str, int]):
    """
    Confirma un extracted_event (status proposed) creando el evento en Google Calendar
    y actualizando Supabase. Recibe {"event_id": <id>}.
    """
    event_id = payload.get("event_id")
    if not event_id:
        raise HTTPException(status_code=400, detail="Falta event_id")

    try:
        res = await confirm_event_tool.execute(event_id=event_id)
        call_id = "confirm-event-1"
        if res.get("success"):
            return AgentResponse(
                text=f"Evento {event_id} confirmado en Google Calendar.",
                tool_calls=[
                    ToolCallInfo(
                        tool_name="confirm_agenda_event",
                        arguments={"event_id": event_id},
                        call_id=call_id,
                    )
                ],
                tool_results=[
                    ToolResultInfo(
                        call_id=call_id,
                        tool_name="confirm_agenda_event",
                        success=True,
                        result=res["result"],
                        error=None,
                    )
                ],
                citations=[],
                debug=AgentDebugInfo(
                    rag_context_used=False,
                    rag_chunk_ids=[],
                    tools_called=["confirm_agenda_event"],
                    iterations=1,
                    latency_ms=0,
                ),
            )
        raise HTTPException(status_code=500, detail=res.get("error") or "No se pudo confirmar el evento")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/calendly/auth_url")
async def calendly_auth_url():
    """
    Devuelve la URL de autorización de Calendly (OAuth).
    """
    if not settings.calendly_client_id or not settings.calendly_redirect_uri:
        raise HTTPException(status_code=400, detail="Faltan CALENDLY_CLIENT_ID o CALENDLY_REDIRECT_URI")
    url = (
        "https://auth.calendly.com/oauth/authorize"
        f"?response_type=code&client_id={settings.calendly_client_id}"
        f"&redirect_uri={settings.calendly_redirect_uri}"
        "&scope=default"
    )
    return {"auth_url": url}


@router.get("/calendly/callback")
async def calendly_callback(code: str, state: str | None = None):
    """
    Intercambia el code de Calendly por un access_token y lo guarda en credentials/calendly_token.json.
    """
    if not settings.calendly_client_id or not settings.calendly_client_secret:
        raise HTTPException(status_code=400, detail="Faltan CALENDLY_CLIENT_ID o CALENDLY_CLIENT_SECRET")
    token_path = Path("credentials/calendly_token.json")
    data = {
        "grant_type": "authorization_code",
        "redirect_uri": settings.calendly_redirect_uri,
        "code": code,
    }
    basic = base64.b64encode(f"{settings.calendly_client_id}:{settings.calendly_client_secret}".encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {basic}",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post("https://auth.calendly.com/oauth/token", data=data, headers=headers)
            resp.raise_for_status()
            token = resp.json()
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(json.dumps(token, indent=2))
        return {"status": "ok", "saved_to": str(token_path)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error intercambiando token: {exc}")


@router.post("/email/send")
async def email_send(payload: Dict[str, str]):
    """
    Envía un email simple usando email_tool.
    Body esperado:
    {
      "to": "dest@example.com",
      "subject": "Asunto",
      "body": "Texto"
    }
    """
    required = ["to", "subject", "body"]
    if not all(k in payload for k in required):
        raise HTTPException(status_code=400, detail="Faltan to, subject o body")
    try:
        res = await email_tool.execute(
            to=payload["to"],
            subject=payload["subject"],
            body=payload["body"],
        )
        if res.get("success"):
            return {"status": "sent", "result": res.get("result")}
        raise HTTPException(status_code=500, detail=res.get("error") or "No se pudo enviar el correo")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/metrics")
async def get_metrics():
    """
    Endpoint para obtener métricas del agente.
    Incluye métricas de tools, RAG, LLM y caché de embeddings.
    """
    from ..services.metrics import metrics_service
    return metrics_service.get_metrics()


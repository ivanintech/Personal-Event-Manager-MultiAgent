import json
import base64
import hmac
import hashlib
from pathlib import Path
from typing import Dict

import httpx
from fastapi import APIRouter, HTTPException
from fastapi import Request

from ..config.settings import get_settings
from ..agents.tools.calendly_list_tool import calendly_list_tool
from ..agents.tools.calendly_ingest_tool import calendly_ingest_tool
from ..agents.tools.calendly_create_tool import calendly_create_tool
from ..config.database import db

router = APIRouter(prefix="/api/v1/calendly", tags=["Calendly"])
settings = get_settings()


@router.get("/auth_url")
async def calendly_auth_url():
    if not settings.calendly_client_id or not settings.calendly_redirect_uri:
        raise HTTPException(status_code=400, detail="Faltan CALENDLY_CLIENT_ID o CALENDLY_REDIRECT_URI")
    url = (
        "https://auth.calendly.com/oauth/authorize"
        f"?response_type=code&client_id={settings.calendly_client_id}"
        f"&redirect_uri={settings.calendly_redirect_uri}"
        "&scope=default"
    )
    return {"auth_url": url}


@router.get("/callback")
async def calendly_callback(code: str, state: str | None = None):
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


@router.get("/events")
async def calendly_events():
    res = await calendly_list_tool.execute()
    if res.get("success"):
        return res["result"]
    raise HTTPException(status_code=500, detail=res.get("error") or "Error listando eventos")


@router.post("/ingest")
async def calendly_ingest():
    """
    Lista eventos en Calendly y los inserta en extracted_events (source=calendly).
    """
    res = await calendly_ingest_tool.execute()
    if res.get("success"):
        return res["result"]
    raise HTTPException(status_code=500, detail=res.get("error") or "Error ingiriendo eventos")


@router.post("/create")
async def calendly_create(payload: Dict[str, str]):
    """
    Crea un evento programado en Calendly.
    Requiere: event_type_uri, invitee_email.
    Opcional: invitee_name, start_time, end_time (ISO).
    """
    required = ["event_type_uri", "invitee_email"]
    if not all(k in payload for k in required):
        raise HTTPException(status_code=400, detail="Faltan event_type_uri o invitee_email")
    res = await calendly_create_tool.execute(
        event_type_uri=payload["event_type_uri"],
        invitee_email=payload["invitee_email"],
        invitee_name=payload.get("invitee_name"),
        start_time=payload.get("start_time"),
        end_time=payload.get("end_time"),
    )
    if res.get("success"):
        return res["result"]
    raise HTTPException(status_code=500, detail=res.get("error") or "Error creando evento en Calendly")


def _validate_signature(secret: str, raw_body: bytes, signature_header: str) -> bool:
    if not secret or not signature_header:
        return False
    try:
        # Calendly envía "sha256=<hex>"
        parts = signature_header.split("=")
        if len(parts) != 2:
            return False
        provided = parts[1]
        mac = hmac.new(secret.encode(), msg=raw_body, digestmod=hashlib.sha256).hexdigest()
        return hmac.compare_digest(provided, mac)
    except Exception:
        return False


@router.post("/refresh_token")
async def calendly_refresh():
    """
    Refresca el token de Calendly usando refresh_token guardado en credentials/calendly_token.json.
    """
    if not settings.calendly_client_id or not settings.calendly_client_secret:
        raise HTTPException(status_code=400, detail="Faltan CALENDLY_CLIENT_ID o CALENDLY_CLIENT_SECRET")
    token_path = Path("credentials/calendly_token.json")
    if not token_path.exists():
        raise HTTPException(status_code=400, detail="No se encontró credentials/calendly_token.json")
    tok = json.loads(token_path.read_text())
    refresh_token = tok.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="El token no tiene refresh_token")

    basic = base64.b64encode(f"{settings.calendly_client_id}:{settings.calendly_client_secret}".encode()).decode()
    headers_r = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {basic}",
    }
    data_r = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp_r = await client.post("https://auth.calendly.com/oauth/token", data=data_r, headers=headers_r)
            resp_r.raise_for_status()
            new_token = resp_r.json()
        token_path.write_text(json.dumps(new_token, indent=2))
        return {"status": "ok", "token": new_token}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error refrescando token: {exc}")


@router.post("/webhook")
async def calendly_webhook(request: Request):
    """
    Webhook receptor de Calendly (invitee.created / invitee.canceled).
    Inserta/actualiza extracted_events con source=calendly.
    Nota: No se valida firma (para pruebas rápidas). Añadir validación HMAC en prod.
    """
    try:
        raw_body = await request.body()
        if settings.calendly_webhook_secret:
            sig_hdr = request.headers.get("Calendly-Webhook-Signature")
            if not _validate_signature(settings.calendly_webhook_secret, raw_body, sig_hdr or ""):
                raise HTTPException(status_code=401, detail="Firma Calendly no válida")

        payload = json.loads(raw_body.decode("utf-8"))
        event = payload.get("event")
        resource = payload.get("payload", {}).get("event", {})
        invitee = payload.get("payload", {}).get("invitee", {})
        status = invitee.get("status") or resource.get("status") or "active"

        title = resource.get("name") or "Calendly event"
        start = resource.get("start_time")
        end = resource.get("end_time")
        uri = resource.get("uri")
        attendees = [invitee.get("email")] if invitee.get("email") else []

        if not start or not end:
            raise HTTPException(status_code=400, detail="Webhook sin start/end time")

        # Insert/update en extracted_events
        rows = [
            {
                "message_id": None,
                "title": title,
                "start_at": start,
                "end_at": end,
                "timezone": None,
                "location": None,
                "attendees": attendees,
                "status": "cancelled" if event == "invitee.canceled" else "proposed",
                "confidence": 0.7,
                "calendar_refs": json.dumps([{"provider": "calendly", "event_uri": uri}]),
                "notes": None,
                "source": "calendly",
            }
        ]
        inserted = await db.insert_extracted_events(rows)
        return {"status": "ok", "event": event, "inserted": inserted}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error en webhook Calendly: {exc}")


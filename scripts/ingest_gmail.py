"""
Ingesta básica de Gmail → Supabase (messages_raw).

Requisitos:
- Haber completado el flujo OAuth con scopes que incluyan Gmail:
  https://www.googleapis.com/auth/gmail.readonly
- Variables de entorno:
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
  GOOGLE_OAUTH_TOKEN_PATH
  (opcional) MAX_RESULTS, LABEL_ID

Uso rápido:
  python scripts/ingest_gmail.py --max 20 --label INBOX
"""

import argparse
import base64
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
GOOGLE_OAUTH_TOKEN_PATH = os.getenv("GOOGLE_OAUTH_TOKEN_PATH", "")

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def require_env():
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SERVICE_ROLE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if not GOOGLE_OAUTH_TOKEN_PATH:
        missing.append("GOOGLE_OAUTH_TOKEN_PATH")
    if missing:
        raise SystemExit(f"Faltan variables: {', '.join(missing)}")


def get_creds():
    return Credentials.from_authorized_user_file(GOOGLE_OAUTH_TOKEN_PATH, scopes=GMAIL_SCOPES)


def header_value(headers: List[Dict[str, str]], name: str) -> Optional[str]:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None


def decode_body(payload: Dict[str, Any]) -> str:
    """
    Busca text/plain; si no, cae a snippet.
    """
    def _walk(p):
        mime = p.get("mimeType", "")
        data = p.get("body", {}).get("data")
        parts = p.get("parts", [])
        if mime == "text/plain" and data:
            try:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            except Exception:
                return ""
        for sub in parts:
            txt = _walk(sub)
            if txt:
                return txt
        return ""

    return _walk(payload) or ""


def fetch_messages(service, max_results: int, label: str) -> List[Dict[str, Any]]:
    msg_list = service.users().messages().list(userId="me", maxResults=max_results, labelIds=[label]).execute()
    ids = msg_list.get("messages", [])
    out = []
    for item in ids:
        msg = service.users().messages().get(userId="me", id=item["id"], format="full").execute()
        out.append(msg)
    return out


def to_iso_ms(ms: Optional[int]) -> Optional[str]:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def build_rows(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for m in messages:
        payload = m.get("payload", {}) or {}
        headers = payload.get("headers", []) or []
        msg_id_header = header_value(headers, "Message-ID") or m.get("id")
        row = {
            "source": "gmail",
            "message_id": msg_id_header,
            "thread_id": m.get("threadId"),
            "from_addr": header_value(headers, "From"),
            "to_addr": header_value(headers, "To"),
            "subject": header_value(headers, "Subject"),
            "body": decode_body(payload) or m.get("snippet"),
            "received_at": to_iso_ms(int(m.get("internalDate"))) if m.get("internalDate") else None,
            "raw_json": m,
        }
        rows.append(row)
    return rows


def upsert_messages(rows: List[Dict[str, Any]]):
    if not rows:
        print("No hay mensajes para insertar.")
        return
    base = f"{SUPABASE_URL}/rest/v1"
    headers = {
        "apikey": SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{base}/messages_raw", headers=headers, json=rows)
        if r.status_code == 409:
            # Ya existen (por la unique source+message_id). Silenciar y mostrar count insertados.
            print("Algunos mensajes ya existían (409). Se omitieron duplicados.")
            try:
                r2 = client.get(f"{base}/messages_raw", headers={**headers, "Prefer": "count=exact"}, params={"select": "id"})
                if r2.status_code == 200:
                    print("messages_raw count:", r2.headers.get("content-range"))
            except Exception:
                pass
            return
        r.raise_for_status()
        print(f"Ingresados {len(r.json())} mensajes en messages_raw.")


def main():
    require_env()

    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=20, help="Número máximo de correos a traer")
    parser.add_argument("--label", type=str, default="INBOX", help="LabelId a usar (ej. INBOX)")
    args = parser.parse_args()

    creds = get_creds()
    service = build("gmail", "v1", credentials=creds)

    messages = fetch_messages(service, max_results=args.max, label=args.label)
    rows = build_rows(messages)
    upsert_messages(rows)


if __name__ == "__main__":
    main()


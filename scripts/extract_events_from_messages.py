"""
Extracción simple de eventos desde messages_raw hacia extracted_events.

Heurística:
- Busca patrones de fecha/hora en subject + body (regex dd/mm/yyyy HH:MM, yyyy-mm-dd HH:MM, HH:MM CET/CEST/UTC).
- Si encuentra hora y fecha, crea start_at/end_at con duración 1h.
- Marca source="gmail", status="proposed", confidence heurístico.
- Evita duplicados por (message_id, title, start_at).

Requisitos:
- Variables: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
- Tabla messages_raw y extracted_events ya creadas.

Uso:
  python scripts/extract_events_from_messages.py --limit 50
"""

import argparse
import os
import re
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}

# Regex sencillos y heurísticas
DATE_TIME_PATTERNS = [
    # 14/12/2025 16:00, 14-12-25 16:00
    r"(?P<d>\d{1,2})[/-](?P<m>\d{1,2})[/-](?P<y>\d{2,4})[ T](?P<h>\d{1,2}):(?P<min>\d{2})(?:[ ]?(?P<tz>(?:UTC|CET|CEST|GMT|[+-]\d{2}:?\d{2})))?",
    # 2025-12-14 16:00
    r"(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})[ T](?P<h>\d{2}):(?P<min>\d{2})(?:[ ]?(?P<tz>(?:UTC|CET|CEST|GMT|[+-]\d{2}:?\d{2})))?",
]
TIME_ONLY = r"(?P<h>\d{1,2}):(?P<min>\d{2})(?:[ ]?(?P<tz>(?:UTC|CET|CEST|GMT|[+-]\d{2}:?\d{2})))?"
TIME_RANGE = r"(?P<h1>\d{1,2}):(?P<m1>\d{2})\s*[-–]\s*(?P<h2>\d{1,2}):(?P<m2>\d{2})(?:[ ]?(?P<tz>(?:UTC|CET|CEST|GMT|[+-]\d{2}:?\d{2})))?"
WEEKDAYS = {
    # español
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
    # inglés
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
}
RELATIVE = {
    "hoy": 0, "today": 0,
    "mañana": 1, "manana": 1, "tomorrow": 1,
}
DEFAULT_TZ = timezone(timedelta(hours=1))  # Europa/Madrid habitual (CET in invierno)


def apply_tz(dt: datetime, tz_token: str | None, default_tz: timezone) -> datetime:
    if not tz_token:
        return dt.replace(tzinfo=default_tz)
    t = tz_token.lower()
    if t in ("cet", "cegt", "cest"):
        return dt.replace(tzinfo=timezone(timedelta(hours=1 if t == "cet" else 2)))
    if t in ("utc", "gmt"):
        return dt.replace(tzinfo=timezone.utc)
    # offsets tipo +0100 o +01:00
    m = re.match(r"([+-])(\d{2}):?(\d{2})", tz_token)
    if m:
        sign = 1 if m.group(1) == "+" else -1
        h = int(m.group(2))
        mi = int(m.group(3))
        return dt.replace(tzinfo=timezone(sign * timedelta(hours=h, minutes=mi)))
    return dt


def next_weekday(from_dt: datetime, target_wd: int) -> datetime:
    days_ahead = (target_wd - from_dt.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    return from_dt + timedelta(days=days_ahead)


def parse_first_datetime(text: str, received_at: datetime | None, default_tz: timezone = DEFAULT_TZ) -> tuple[datetime | None, datetime | None]:
    text = text or ""
    text_lower = text.lower()

    # Rango explícito hh:mm-hh:mm
    m_range = re.search(TIME_RANGE, text)
    if m_range:
        gd = m_range.groupdict()
        base = received_at or datetime.now(default_tz)
        tz_tok = gd.get("tz")
        start = base.replace(hour=int(gd["h1"]), minute=int(gd["m1"]), second=0, microsecond=0)
        end = base.replace(hour=int(gd["h2"]), minute=int(gd["m2"]), second=0, microsecond=0)
        start = apply_tz(start, tz_tok, default_tz)
        end = apply_tz(end, tz_tok, default_tz)
        # weekday relativo
        for wd_name, wd_idx in WEEKDAYS.items():
            if wd_name in text_lower:
                start = next_weekday(start, wd_idx)
                end = next_weekday(end, wd_idx)
                break
        # relativo hoy/mañana
        for rel, offset in RELATIVE.items():
            if rel in text_lower:
                start = start + timedelta(days=offset)
                end = end + timedelta(days=offset)
                break
        return start, end

    for pat in DATE_TIME_PATTERNS:
        m = re.search(pat, text)
        if m:
            gd = m.groupdict()
            y = int(gd["y"])
            if y < 100:
                y += 2000
            start = datetime(
                y,
                int(gd["m"]),
                int(gd["d"]),
                int(gd["h"]),
                int(gd["min"]),
                tzinfo=default_tz,
            )
            start = apply_tz(start, gd.get("tz"), default_tz)
            # relativo (por si aparece "mañana" junto a fecha corta sin año)
            for rel, offset in RELATIVE.items():
                if rel in text_lower:
                    start = start + timedelta(days=offset)
                    break
            return start, None
    # si solo hay hora, asumimos hoy
    m = re.search(TIME_ONLY, text)
    if m:
        base = received_at or datetime.now(timezone.utc)
        tz_tok = m.groupdict().get("tz")
        start = base.replace(hour=int(m.group("h")), minute=int(m.group("min")), second=0, microsecond=0)
        start = apply_tz(start, tz_tok, default_tz)
        # si hay weekday en texto, ajustar al siguiente
        for wd_name, wd_idx in WEEKDAYS.items():
            if wd_name in text_lower:
                start = next_weekday(start, wd_idx)
                break
        # relativo hoy/mañana
        for rel, offset in RELATIVE.items():
            if rel in text_lower:
                start = start + timedelta(days=offset)
                break
        end = start + timedelta(hours=1)
        return start, end
    return None, None


def fetch_messages(limit: int):
    with httpx.Client(timeout=20) as client:
        r = client.get(
            f"{BASE}/messages_raw",
            headers=HEADERS,
            params={"select": "id,message_id,subject,body,received_at,source", "order": "received_at.desc", "limit": str(limit)},
        )
        r.raise_for_status()
        return r.json()


def existing_keys():
    with httpx.Client(timeout=20) as client:
        r = client.get(
            f"{BASE}/extracted_events",
            headers=HEADERS,
            params={"select": "message_id,title,start_at"},
        )
        r.raise_for_status()
        rows = r.json()
        keys = {(row.get("message_id"), row.get("title"), row.get("start_at")) for row in rows}
        return keys


def insert_events(events):
    if not events:
        print("No hay eventos nuevos.")
        return
    with httpx.Client(timeout=20) as client:
        r = client.post(
            f"{BASE}/extracted_events",
            headers={**HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"},
            json=events,
        )
        if r.status_code >= 400:
            print("Error insertando events:", r.text)
            r.raise_for_status()
        print(f"Insertados {len(r.json())} eventos en extracted_events.")


def main():
    if not SUPABASE_URL or not SERVICE_ROLE_KEY:
        raise SystemExit("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50, help="Mensajes recientes a procesar")
    args = parser.parse_args()

    msgs = fetch_messages(limit=args.limit)
    existing = existing_keys()
    new_events = []

    for msg in msgs:
        subj = msg.get("subject") or ""
        body = msg.get("body") or ""
        text = f"{subj}\n{body}"
        recv = None
        if msg.get("received_at"):
            try:
                recv = datetime.fromisoformat(msg["received_at"].replace("Z", "+00:00"))
            except Exception:
                recv = None
        start, end = parse_first_datetime(text, recv)
        if not start:
            continue
        if not end:
            end = start + timedelta(hours=1)
        title = subj.strip() or "Evento"
        key = (msg.get("message_id"), title, start.isoformat())
        if key in existing:
            continue
        ev = {
            "message_id": msg.get("id"),
            "title": title,
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
            "timezone": "UTC",
            "location": None,
            "attendees": None,
            "status": "proposed",
            "confidence": 0.4,
        }
        # Opcional: si la columna source existe, incluirla (la tabla ya la define el init SQL)
        ev["source"] = msg.get("source") or "gmail"
        new_events.append(ev)

    insert_events(new_events)


if __name__ == "__main__":
    main()


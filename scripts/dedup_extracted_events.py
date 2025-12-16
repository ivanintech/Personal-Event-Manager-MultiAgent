"""
Deduplicación simple de extracted_events en Supabase.

Regla:
- Agrupa por source + título normalizado (lower, strip).
- Dentro de cada grupo, ordena por start_at; elimina eventos cuya start_at
  esté a menos de 90 minutos de otro ya aceptado (misma fuente/título).
- Conserva los más antiguos primero.

Uso:
  python scripts/dedup_extracted_events.py
"""

import os
from datetime import datetime, timezone

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

WINDOW_MINUTES = 90


def fetch_events():
    with httpx.Client(timeout=20) as client:
        r = client.get(
            f"{BASE}/extracted_events",
            headers=HEADERS,
            params={"select": "id,title,start_at,source", "order": "start_at.asc"},
        )
        r.raise_for_status()
        return r.json()


def delete_ids(ids):
    if not ids:
        return
    with httpx.Client(timeout=20) as client:
        r = client.request(
            "DELETE",
            f"{BASE}/extracted_events",
            headers=HEADERS,
            params={"id": "in.({})".format(",".join(map(str, ids)))},
        )
        r.raise_for_status()
        print(f"Borrados {len(ids)} duplicados.")


def main():
    if not SUPABASE_URL or not SERVICE_ROLE_KEY:
        raise SystemExit("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")

    events = fetch_events()
    groups = {}
    for ev in events:
        title_norm = (ev.get("title") or "").strip().lower()
        source = ev.get("source") or "extracted"
        key = (source, title_norm)
        groups.setdefault(key, []).append(ev)

    to_delete = []
    for key, evs in groups.items():
        kept = []
        for ev in evs:
            try:
                start = datetime.fromisoformat(ev["start_at"].replace("Z", "+00:00"))
            except Exception:
                start = None
            is_dup = False
            for kv in kept:
                try:
                    kv_start = datetime.fromisoformat(kv["start_at"].replace("Z", "+00:00"))
                except Exception:
                    kv_start = None
                if start and kv_start:
                    delta = abs((start - kv_start).total_seconds()) / 60
                    if delta <= WINDOW_MINUTES:
                        is_dup = True
                        break
            if is_dup:
                to_delete.append(ev["id"])
            else:
                kept.append(ev)

    delete_ids(to_delete)


if __name__ == "__main__":
    main()









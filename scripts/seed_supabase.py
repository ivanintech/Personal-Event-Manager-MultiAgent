"""
Seed data for Supabase (demo/testing).

Creates demo rows for:
- rag_chunks (with embedding length 1024)
- messages_raw (2 sample messages)
- importance_labels (linked to messages)
- extracted_events (proposed events)

Cleanup: deletes previous demo rows tagged with source='seed-demo' before inserting.
"""

import os
import json
import random
import httpx


SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SERVICE_ROLE_KEY:
    raise SystemExit("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing in environment")

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}
RETURN_HEADERS = {**HEADERS, "Prefer": "return=representation"}


def delete_demo_rows():
    with httpx.Client(timeout=30) as client:
        # Delete rag_chunks first (tagged by source)
        client.request(
            "DELETE",
            f"{BASE}/rag_chunks",
            headers=HEADERS,
            params={"source": "eq.seed-demo"},
        )
        # Delete messages_raw (cascade will remove extracted_events/importance_labels)
        client.request(
            "DELETE",
            f"{BASE}/messages_raw",
            headers=HEADERS,
            params={"source": "eq.seed-demo"},
        )


def seed_rag_chunks():
    emb = [0.0] * 1024  # demo embedding, dimension 1024
    rows = [
        {
            "chunk_id": "seed-chunk-1",
            "source": "seed-demo",
            "text": "Reunión con el equipo de producto para revisar roadmap Q3.",
            "embedding": emb,
        },
        {
            "chunk_id": "seed-chunk-2",
            "source": "seed-demo",
            "text": "Demo con cliente ACME el viernes a las 10:00 CET.",
            "embedding": emb,
        },
    ]
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/rag_chunks", headers=RETURN_HEADERS, json=rows)
        r.raise_for_status()
        return r.json()


def seed_messages_and_events():
    messages = [
        {
            "source": "seed-demo",
            "message_id": "demo-msg-1",
            "thread_id": "demo-thread-1",
            "from_addr": "cliente@acme.com",
            "to_addr": "user@example.com",
            "subject": "Confirmación demo viernes",
            "body": "Hola, confirmamos demo el viernes a las 10:00 CET con el equipo.",
            "received_at": "2025-12-15T09:00:00Z",
        },
        {
            "source": "seed-demo",
            "message_id": "demo-msg-2",
            "thread_id": "demo-thread-2",
            "from_addr": "recruiter@talent.com",
            "to_addr": "user@example.com",
            "subject": "Entrevista técnica martes",
            "body": "¿Puedes el martes a las 16:00 CET para una entrevista técnica?",
            "received_at": "2025-12-16T09:00:00Z",
        },
    ]
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/messages_raw", headers=RETURN_HEADERS, json=messages)
        r.raise_for_status()
        msgs = r.json()

        # Importance labels
        labels = [
            {
                "message_id": msgs[0]["id"],
                "label": "important",
                "score": 0.92,
                "rationale": "Demo con cliente estratégico ACME.",
            },
            {
                "message_id": msgs[1]["id"],
                "label": "important",
                "score": 0.88,
                "rationale": "Entrevista técnica prioritaria.",
            },
        ]
        r = client.post(f"{BASE}/importance_labels", headers=RETURN_HEADERS, json=labels)
        r.raise_for_status()

        # Extracted events (proposed)
        events = [
            {
                "message_id": msgs[0]["id"],
                "title": "Demo con ACME",
                "start_at": "2025-12-19T10:00:00+01:00",
                "end_at": "2025-12-19T11:00:00+01:00",
                "timezone": "Europe/Madrid",
                "location": "Zoom",
                "attendees": json.dumps(["cliente@acme.com", "user@example.com"]),
                "status": "proposed",
                "confidence": 0.86,
            },
            {
                "message_id": msgs[1]["id"],
                "title": "Entrevista técnica",
                "start_at": "2025-12-16T16:00:00+01:00",
                "end_at": "2025-12-16T17:00:00+01:00",
                "timezone": "Europe/Madrid",
                "location": "Google Meet",
                "attendees": json.dumps(["recruiter@talent.com", "user@example.com"]),
                "status": "proposed",
                "confidence": 0.83,
            },
        ]
        r = client.post(f"{BASE}/extracted_events", headers=RETURN_HEADERS, json=events)
        r.raise_for_status()

        return {"messages": msgs}


def main():
    delete_demo_rows()
    seed_rag_chunks()
    seed_messages_and_events()
    print("Seed completed (seed-demo).")


if __name__ == "__main__":
    main()









"""
Script helper para probar webhook de Calendly con ngrok.
"""

import asyncio
import httpx
import json
from pathlib import Path
from datetime import datetime
import hmac
import hashlib

# Configuración
WEBHOOK_SECRET = "your_webhook_secret"  # Debe coincidir con CALENDLY_WEBHOOK_SECRET
NGROK_URL = "https://your-ngrok-url.ngrok.io"  # URL pública de ngrok
WEBHOOK_ENDPOINT = f"{NGROK_URL}/api/v1/calendly/webhook"


def generate_hmac_signature(payload: str, secret: str) -> str:
    """Genera firma HMAC para validación."""
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


async def test_webhook_invitee_created():
    """Test de webhook invitee.created."""
    # Payload de ejemplo según Calendly API
    payload = {
        "event": "invitee.created",
        "time": datetime.utcnow().isoformat() + "Z",
        "payload": {
            "event_type": {
                "uri": "https://api.calendly.com/event_types/ABC123",
                "name": "30 Minute Meeting",
            },
            "event": {
                "uri": "https://api.calendly.com/scheduled_events/DEF456",
                "name": "Meeting with John",
                "start_time": (datetime.utcnow().replace(hour=10, minute=0)).isoformat() + "Z",
                "end_time": (datetime.utcnow().replace(hour=10, minute=30)).isoformat() + "Z",
            },
            "invitee": {
                "uri": "https://api.calendly.com/invitees/XYZ789",
                "name": "John Doe",
                "email": "john@example.com",
            },
        },
    }
    
    payload_str = json.dumps(payload, sort_keys=True)
    signature = generate_hmac_signature(payload_str, WEBHOOK_SECRET)
    
    headers = {
        "Content-Type": "application/json",
        "Calendly-Webhook-Signature": signature,
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                WEBHOOK_ENDPOINT,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            print(f"✅ Webhook invitee.created OK: {resp.json()}")
        except httpx.HTTPError as e:
            print(f"❌ Error: {e}")
            if hasattr(e, "response"):
                print(f"Response: {e.response.text}")


async def test_webhook_invitee_canceled():
    """Test de webhook invitee.canceled."""
    payload = {
        "event": "invitee.canceled",
        "time": datetime.utcnow().isoformat() + "Z",
        "payload": {
            "event_type": {
                "uri": "https://api.calendly.com/event_types/ABC123",
            },
            "event": {
                "uri": "https://api.calendly.com/scheduled_events/DEF456",
            },
            "invitee": {
                "uri": "https://api.calendly.com/invitees/XYZ789",
            },
        },
    }
    
    payload_str = json.dumps(payload, sort_keys=True)
    signature = generate_hmac_signature(payload_str, WEBHOOK_SECRET)
    
    headers = {
        "Content-Type": "application/json",
        "Calendly-Webhook-Signature": signature,
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                WEBHOOK_ENDPOINT,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            print(f"✅ Webhook invitee.canceled OK: {resp.json()}")
        except httpx.HTTPError as e:
            print(f"❌ Error: {e}")
            if hasattr(e, "response"):
                print(f"Response: {e.response.text}")


async def main():
    """Ejecuta tests de webhook."""
    print("🧪 Testing Calendly Webhook")
    print(f"Endpoint: {WEBHOOK_ENDPOINT}")
    print(f"Secret: {WEBHOOK_SECRET[:10]}...")
    print()
    
    print("1. Testing invitee.created...")
    await test_webhook_invitee_created()
    print()
    
    print("2. Testing invitee.canceled...")
    await test_webhook_invitee_canceled()
    print()
    
    print("✅ Tests completados")


if __name__ == "__main__":
    asyncio.run(main())








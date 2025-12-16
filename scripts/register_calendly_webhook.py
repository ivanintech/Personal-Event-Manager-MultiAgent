"""
Registra un webhook de Calendly (invitee.created / invitee.canceled) usando el token guardado.

Requisitos:
- credentials/calendly_token.json con access_token y organization (o user)
- CALENDLY_WEBHOOK_SECRET en .env (o pasado por CLI)

Uso:
  python scripts/register_calendly_webhook.py --public-url https://<ngrok-id>.ngrok.io --scope organization
"""

import argparse
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-url", required=True, help="URL pública (ej. https://xxxx.ngrok.io)")
    parser.add_argument("--scope", choices=["organization", "user"], default="organization")
    args = parser.parse_args()

    secret = os.getenv("CALENDLY_WEBHOOK_SECRET", "")
    if not secret:
        raise SystemExit("Falta CALENDLY_WEBHOOK_SECRET en entorno")

    tok_path = Path("credentials/calendly_token.json")
    if not tok_path.exists():
        raise SystemExit("No se encontró credentials/calendly_token.json")
    tok = json.loads(tok_path.read_text())
    access_token = tok.get("access_token")
    if not access_token:
        raise SystemExit("El token no tiene access_token")

    target = f"{args.public_url.rstrip('/')}/api/v1/calendly/webhook"
    payload = {
        "url": target,
        "events": ["invitee.created", "invitee.canceled"],
        "signing_key": secret,
    }
    if args.scope == "organization":
        org = tok.get("organization")
        if not org:
            raise SystemExit("El token no trae 'organization'; usa scope user o actualiza token.")
        payload["organization"] = org
        payload["scope"] = "organization"
    else:
        user = tok.get("owner")
        if not user:
            raise SystemExit("El token no trae 'owner'; usa scope organization o actualiza token.")
        payload["user"] = user
        payload["scope"] = "user"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=20) as client:
            r = client.post("https://api.calendly.com/webhook_subscriptions", headers=headers, json=payload)
            r.raise_for_status()
            print("Webhook registrado:", r.json())
    except Exception as e:
        print("Error registrando webhook:", e)


if __name__ == "__main__":
    main()









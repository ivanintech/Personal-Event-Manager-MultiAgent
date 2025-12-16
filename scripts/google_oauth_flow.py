import os
import json
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Scopes que necesitamos: Calendar + Gmail (modificar)
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
]

def main():
    load_dotenv()

    client_path = os.getenv("GOOGLE_OAUTH_CLIENT_PATH", "credentials/google_oauth_client.json")
    token_path = os.getenv("GOOGLE_OAUTH_TOKEN_PATH", "credentials/google_oauth_token.json")
    redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/")

    client_path = Path(client_path)
    token_path = Path(token_path)

    if not client_path.exists():
        raise FileNotFoundError(f"GOOGLE_OAUTH_CLIENT_PATH no existe: {client_path}")

    creds = None

    # Si ya existe token, intenta refrescar
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("Token refrescado correctamente.")
            except Exception as e:
                print(f"Error refrescando token, se lanzará flujo nuevo: {e}")
                creds = None

    # Si no hay credenciales válidas, iniciamos flujo OAuth
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_path), SCOPES, redirect_uri=redirect_uri
        )
        # Esto abre navegador y usa el redirect_uri (por defecto http://localhost:8000/)
        # El puerto debe coincidir con el redirect_uri registrado en Google Cloud.
        port = 8000
        try:
            port = int(redirect_uri.split(":")[-1].rstrip("/"))
        except Exception:
            port = 8000
        creds = flow.run_local_server(port=port, prompt="consent")

        # Guardamos token en disco
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with token_path.open("w") as token_file:
            token_file.write(creds.to_json())
        print(f"Nuevo token guardado en: {token_path}")

    # Mostrar info básica para verificar
    info = {
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "scopes": creds.scopes,
    }
    print("Credenciales válidas generadas:")
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()

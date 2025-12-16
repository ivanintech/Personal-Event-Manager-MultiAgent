"""
Backend STT basado en Whisper (Groq u OpenAI).
Primera versión: solo transcribe_sync; transcribe_stream reusa la sync.
"""

from typing import AsyncIterator, Iterable
import logging
import base64

from .base import STTBackend
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


class WhisperSTTBackend(STTBackend):
    def __init__(self):
        settings = get_settings()
        self.provider = settings.stt_provider
        self.groq_api_key = settings.groq_api_key
        self.groq_model = settings.groq_whisper_model or "whisper-large-v3"
        self.openai_api_key = settings.openai_api_key
        self.openai_model = settings.openai_whisper_model or "whisper-1"

    async def transcribe_stream(self, audio_chunks: Iterable[bytes]) -> AsyncIterator[str]:
        # Por simplicidad, junta los chunks y usa la sync
        audio_bytes = b"".join(audio_chunks)
        yield self.transcribe_sync(audio_bytes)

    def transcribe_sync(self, audio_bytes: bytes) -> str:
        """
        Llamada síncrona simple:
        - Si provider=groq: POST https://api.groq.com/openai/v1/audio/transcriptions
        - Si provider=openai: POST https://api.openai.com/v1/audio/transcriptions
        Retorna texto o string vacío si falla.
        """
        if not audio_bytes:
            logger.warning("⚠️ Audio vacío recibido en STT")
            return ""

        logger.info(f"🎤 STT: Audio recibido: {len(audio_bytes)} bytes")

        try:
            import httpx
        except ImportError:
            logger.error("httpx no instalado; no se puede hacer STT real")
            return ""

        try:
            if self.provider == "groq":
                if not self.groq_api_key:
                    logger.error("❌ GROQ_API_KEY no configurada")
                    return ""
                url = "https://api.groq.com/openai/v1/audio/transcriptions"
                headers = {"Authorization": f"Bearer {self.groq_api_key}"}
                files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
                data = {"model": self.groq_model}
                logger.info(f"📡 Enviando a Groq STT: {len(audio_bytes)} bytes, modelo: {self.groq_model}")
            elif self.provider == "openai":
                if not self.openai_api_key:
                    logger.error("❌ OPENAI_API_KEY no configurada")
                    return ""
                url = "https://api.openai.com/v1/audio/transcriptions"
                headers = {"Authorization": f"Bearer {self.openai_api_key}"}
                files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
                data = {"model": self.openai_model}
                logger.info(f"📡 Enviando a OpenAI STT: {len(audio_bytes)} bytes, modelo: {self.openai_model}")
            else:
                logger.warning("⚠️ Provider STT desconocido: {self.provider}, usando mock")
                return "Transcripción (mock STT)."

            resp = httpx.post(url, headers=headers, data=data, files=files, timeout=60)
            logger.info(f"📥 STT respuesta: {resp.status_code}")
            
            if resp.status_code != 200:
                logger.error(f"❌ STT error HTTP {resp.status_code}: {resp.text}")
            
            resp.raise_for_status()
            result = resp.json().get("text", "")
            logger.info(f"✅ STT transcribió: '{result}' ({len(result)} caracteres)")
            return result
        except httpx.HTTPStatusError as exc:
            logger.error(f"❌ Error HTTP en STT: {exc.response.status_code} - {exc.response.text}")
            return ""
        except Exception as exc:  # pragma: no cover - manejo de error externo
            logger.error(f"❌ Error en STT Whisper: {exc}", exc_info=True)
            return ""





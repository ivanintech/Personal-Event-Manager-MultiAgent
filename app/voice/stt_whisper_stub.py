"""
Stub para integración STT (Whisper/Groq u otro provider).
Mantiene la interfaz STTBackend.
"""

from typing import AsyncIterator, Iterable

from .base import STTBackend


class WhisperSTTBackend(STTBackend):
    def __init__(self, provider: str = "groq"):
        self.provider = provider

    async def transcribe_stream(self, audio_chunks: Iterable[bytes]) -> AsyncIterator[str]:
        # TODO: implementar streaming real; por ahora retorna placeholder
        for _ in audio_chunks:
            yield "Transcripción (Whisper stub)"

    def transcribe_sync(self, audio_bytes: bytes) -> str:
        # TODO: llamada sync al provider
        return "Transcripción (Whisper stub)"










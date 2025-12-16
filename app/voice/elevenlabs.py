"""
Stub de TTS para ElevenLabs.
En el futuro: usar SDK oficial o HTTP; este stub mantiene la interfaz.
"""

from typing import AsyncIterator

from .base import TTSBackend


class ElevenLabsTTSBackend(TTSBackend):
    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        # TODO: implementar llamada streaming a ElevenLabs
        yield self.synthesize_sync(text)

    def synthesize_sync(self, text: str) -> bytes:
        # TODO: implementar llamada sin streaming a ElevenLabs
        return text.encode("utf-8")









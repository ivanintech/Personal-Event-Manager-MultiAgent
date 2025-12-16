from typing import AsyncIterator, Iterable


class STTBackend:
    """Interfaz para motores de STT."""

    async def transcribe_stream(self, audio_chunks: Iterable[bytes]) -> AsyncIterator[str]:
        """Recibe chunks de audio y produce segmentos de texto."""
        raise NotImplementedError

    def transcribe_sync(self, audio_bytes: bytes) -> str:
        """Transcribe audio completo en modo bloqueante."""
        raise NotImplementedError


class TTSBackend:
    """Interfaz para motores de TTS."""

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Genera audio en streaming a partir de texto."""
        raise NotImplementedError

    def synthesize_sync(self, text: str) -> bytes:
        """Genera audio completo en modo bloqueante."""
        raise NotImplementedError










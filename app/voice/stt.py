import asyncio
from typing import AsyncGenerator, Iterable


class BaseSTT:
    """Interfaz de STT en streaming."""

    async def transcribe_stream(self, audio_chunks: Iterable[bytes]) -> AsyncGenerator[str, None]:
        raise NotImplementedError


class MockSTT(BaseSTT):
    """STT de prueba: devuelve una frase fija por lote de audio."""

    async def transcribe_stream(self, audio_chunks: Iterable[bytes]) -> AsyncGenerator[str, None]:
        for _ in audio_chunks:
            await asyncio.sleep(0)  # ceder control
            yield "Transcripción simulada (mock)."


def get_stt_client(use_mock: bool = True) -> BaseSTT:
    # En siguientes iteraciones: Groq Whisper u otro proveedor
    if use_mock:
        return MockSTT()
    raise NotImplementedError("Implementar STT real")










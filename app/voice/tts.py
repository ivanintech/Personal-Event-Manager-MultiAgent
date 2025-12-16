import asyncio
from typing import AsyncGenerator


class BaseTTS:
    """Interfaz de TTS en streaming."""

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        raise NotImplementedError


class MockTTS(BaseTTS):
    """TTS de prueba: devuelve bytes de texto codificado."""

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        # Simula streaming en dos trozos
        for chunk in [text[: len(text)//2], text[len(text)//2 :]]:
            await asyncio.sleep(0)
            yield chunk.encode("utf-8")


def get_tts_client(use_mock: bool = True) -> BaseTTS:
    # En siguientes iteraciones: ElevenLabs/VibeVoice streaming
    if use_mock:
        return MockTTS()
    raise NotImplementedError("Implementar TTS real")










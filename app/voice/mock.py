import asyncio
from typing import AsyncIterator, Iterable

from .base import STTBackend, TTSBackend


class MockSTT(STTBackend):
    """STT de prueba: devuelve una frase fija por chunk."""

    async def transcribe_stream(self, audio_chunks: Iterable[bytes]) -> AsyncIterator[str]:
        for _ in audio_chunks:
            await asyncio.sleep(0)
            yield "Transcripción simulada (mock)."

    def transcribe_sync(self, audio_bytes: bytes) -> str:
        return "Transcripción simulada (mock)."


class MockTTS(TTSBackend):
    """
    TTS de prueba: genera audio PCM16 simulado (silence con tono suave).
    Útil cuando VibeVoice no está disponible.
    """

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """
        Genera chunks de audio PCM16 simulado.
        Cada chunk es silencio con un tono suave para simular audio.
        """
        import struct
        import math
        
        # Configuración de audio simulado
        sample_rate = 24000
        duration_per_chunk = 0.1  # 100ms por chunk
        samples_per_chunk = int(sample_rate * duration_per_chunk)
        total_duration = min(len(text) * 0.05, 3.0)  # Máximo 3 segundos
        total_chunks = int(total_duration / duration_per_chunk)
        
        # Generar chunks de audio PCM16 (silencio con tono muy suave)
        for i in range(total_chunks):
            chunk_data = bytearray()
            for j in range(samples_per_chunk):
                # Generar un tono muy suave (casi silencio) para simular audio
                # Frecuencia muy baja para que sea apenas audible
                sample = int(100 * math.sin(2 * math.pi * 440 * (i * duration_per_chunk + j / sample_rate)))
                # Limitar a rango PCM16 (-32768 a 32767)
                sample = max(-32768, min(32767, sample))
                chunk_data.extend(struct.pack('<h', sample))
            
            await asyncio.sleep(0.01)  # Pequeño delay para simular streaming
            yield bytes(chunk_data)

    def synthesize_sync(self, text: str) -> bytes:
        """Genera audio completo de forma síncrona."""
        import struct
        import math
        
        sample_rate = 24000
        duration = min(len(text) * 0.05, 3.0)
        samples = int(sample_rate * duration)
        
        audio_data = bytearray()
        for i in range(samples):
            sample = int(100 * math.sin(2 * math.pi * 440 * i / sample_rate))
            sample = max(-32768, min(32767, sample))
            audio_data.extend(struct.pack('<h', sample))
        
        return bytes(audio_data)






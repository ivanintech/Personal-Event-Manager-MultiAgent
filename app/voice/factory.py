from .base import STTBackend, TTSBackend
from .mock import MockSTT, MockTTS
from .vibevoice import VibeVoiceTTSBackend
from .elevenlabs import ElevenLabsTTSBackend
from .stt_whisper import WhisperSTTBackend
from ..config.settings import get_settings


def get_stt_backend() -> STTBackend:
    settings = get_settings()
    backend = settings.voice_stt_backend.lower()
    if backend == "whisper":
        return WhisperSTTBackend()
    return MockSTT()


def get_tts_backend() -> TTSBackend:
    settings = get_settings()
    backend = settings.voice_tts_backend.lower()
    if backend == "vibevoice":
        return VibeVoiceTTSBackend()
    if backend == "elevenlabs":
        return ElevenLabsTTSBackend()
    return MockTTS()


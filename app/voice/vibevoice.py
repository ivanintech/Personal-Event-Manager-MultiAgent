"""
Backend TTS para VibeVoice (-Realtime) con streaming WebSocket.

Diseño:
- Config vía core/config.py (.env):
    VOICE_TTS_BACKEND=vibevoice
    VIBEVOICE_BASE_URL=http(s)://host:port
    VIBEVOICE_MODEL=<opcional>
- Streaming WebSocket:
    Conecta a {base_url}/stream?text=...&voice=... y recibe chunks PCM16 en tiempo real.
- Fallback HTTP:
    Si WebSocket falla, intenta POST {base_url}/tts (compatibilidad).
"""

from typing import AsyncIterator, Optional
import logging
import json
import asyncio
import re
from urllib.parse import urlencode

from .base import TTSBackend
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


class VibeVoiceTTSBackend(TTSBackend):
    """
    Backend TTS para VibeVoice-Realtime con streaming WebSocket.
    Basado en la implementación de VibeVoice/demo/web/app.py.
    """

    def __init__(self):
        settings = get_settings()
        self.base_url: Optional[str] = settings.vibevoice_base_url or None
        self.model: Optional[str] = settings.vibevoice_model or None
        self._use_websocket = True  # Preferir WebSocket para streaming real

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """
        Streaming real vía WebSocket: conecta a /stream y recibe chunks PCM16.
        Si falla, intenta fallback HTTP.
        """
        if not self.base_url:
            logger.warning("VibeVoice base_url no configurado; devolviendo texto plano")
            yield text.encode("utf-8")
            return

        # Intentar VibeVoice solo una vez - si está ocupado, fallar inmediatamente para usar Web Speech API
        max_retries = 1  # Solo un intento - no esperar
        retry_delay = 0.5  # Delay mínimo solo para el primer intento
        
        for attempt in range(max_retries):
            if self._use_websocket:
                try:
                    async for chunk in self._synthesize_websocket(text):
                        yield chunk
                    return  # Éxito, salir
                except RuntimeError as exc:
                    error_msg = str(exc)
                    # Si es "Service busy", fallar inmediatamente - no esperar
                    if "busy" in error_msg.lower() or "1013" in error_msg or "backend_busy" in error_msg:
                        logger.warning(f"⚠️ VibeVoice ocupado - fallando inmediatamente para usar Web Speech API")
                        logger.info(f"💡 VibeVoice está ocupado. El frontend usará Web Speech API como fallback.")
                        # No devolver silencio, dejar que el frontend use Web Speech API
                        return  # Salir sin yield para que el frontend detecte el error
                    else:
                        # Otro error, no reintentar
                        logger.warning(f"⚠️ VibeVoice: WebSocket streaming falló: {exc}, intentando HTTP fallback")
                        self._use_websocket = False  # Desactivar WS temporalmente
                except Exception as exc:
                    logger.warning(f"⚠️ VibeVoice: WebSocket streaming falló: {exc}, intentando HTTP fallback")
                    self._use_websocket = False  # Desactivar WS temporalmente

        # Fallback: Intentar ElevenLabs si está configurado
        settings = get_settings()
        if settings.elevenlabs_api_key and settings.voice_tts_backend != "vibevoice":
            logger.info("🔄 VibeVoice falló, intentando ElevenLabs como fallback...")
            try:
                from .elevenlabs import ElevenLabsTTSBackend
                elevenlabs_backend = ElevenLabsTTSBackend()
                async for chunk in elevenlabs_backend.synthesize_stream(text):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"⚠️ ElevenLabs fallback también falló: {e}")
        
        # Último fallback: silencio
        logger.warning("⚠️ VibeVoice: Todos los fallbacks fallaron, devolviendo silencio")
        yield b"\x00\x00" * 48000 # 1 segundo de silencio PCM16

    async def _synthesize_websocket(self, text: str) -> AsyncIterator[bytes]:
        """
        Conecta al WebSocket de VibeVoice y recibe chunks PCM16 en streaming.
        Basado en VibeVoice/demo/web/app.py websocket_stream.
        """
        try:
            import websockets
        except ImportError:
            raise ImportError("websockets no instalado; instala websockets para streaming")

        # Construir URL WebSocket
        ws_url = self.base_url.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
        
        # Limpiar y truncar texto si es muy largo (las URLs tienen límites)
        # VibeVoice puede tener problemas con textos muy largos o caracteres especiales
        cleaned_text = text.strip()
        
        # Remover emojis y caracteres especiales que pueden causar problemas
        # Remover emojis (Unicode ranges comunes)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        cleaned_text = emoji_pattern.sub('', cleaned_text)
        
        # Remover markdown formatting que puede causar problemas
        cleaned_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned_text)  # **bold**
        cleaned_text = re.sub(r'\*([^*]+)\*', r'\1', cleaned_text)  # *italic*
        cleaned_text = re.sub(r'`([^`]+)`', r'\1', cleaned_text)  # `code`
        
        # Limpiar espacios múltiples
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        # Para textos muy largos, tomar solo las primeras frases completas
        max_text_length = 1500  # Reducir límite para evitar problemas con URLs largas
        
        if len(cleaned_text) > max_text_length:
            logger.warning(f"⚠️ VibeVoice: Texto muy largo ({len(cleaned_text)} chars), truncando a {max_text_length}...")
            # Truncar en el último punto, signo de interrogación o exclamación antes del límite
            truncated = cleaned_text[:max_text_length]
            last_sentence_end = max(
                truncated.rfind('.'),
                truncated.rfind('?'),
                truncated.rfind('!')
            )
            if last_sentence_end > max_text_length * 0.7:  # Si encontramos un punto cerca del final
                cleaned_text = truncated[:last_sentence_end + 1]
            else:
                # Si no hay punto cercano, truncar normalmente
                cleaned_text = truncated + "..."
        
        if not cleaned_text:
            logger.error("❌ VibeVoice: Texto vacío después de limpieza")
            raise ValueError("Texto vacío después de limpiar emojis y caracteres especiales")
        
        params = {"text": cleaned_text}
        # Solo pasar "voice" si es un nombre de voz válido (no el nombre del modelo)
        # Si self.model es "VibeVoice-Realtime-0.5B" o similar, no pasarlo
        # VibeVoice usará la voz por defecto automáticamente
        if self.model and not any(x in self.model.lower() for x in ["vibevoice", "realtime", "0.5b", "model"]):
            # Parece un nombre de voz válido (ej: "en-Carter_man")
            params["voice"] = self.model
            logger.debug(f"🎤 VibeVoice: Usando voz personalizada: {self.model}")
        else:
            logger.debug("🎤 VibeVoice: Usando voz por defecto del servidor")
        
        ws_url = f"{ws_url}/stream?{urlencode(params)}"
        
        # Verificar que la URL no sea demasiado larga
        if len(ws_url) > 8000:  # Límite típico de URLs
            logger.error(f"❌ VibeVoice: URL demasiado larga ({len(ws_url)} chars)")
            raise ValueError(f"URL demasiado larga para WebSocket: {len(ws_url)} caracteres")
        
        logger.info(f"🔵 VibeVoice: Conectando a WebSocket (URL: {len(ws_url)} chars)")
        logger.info(f"📝 VibeVoice: Texto a sintetizar ({len(cleaned_text)} chars): {cleaned_text[:100]}...")
        logger.debug(f"🔗 VibeVoice: URL completa: {ws_url[:200]}...")
        
        try:
            logger.info(f"🔌 VibeVoice: Iniciando conexión WebSocket...")
            # Aumentar timeout y añadir ping_interval para mantener la conexión viva
            # IMPORTANTE: VibeVoice solo permite UNA conexión a la vez (tiene un lock)
            # Si está ocupado, esperamos más tiempo antes de reintentar
            async with websockets.connect(
                ws_url, 
                timeout=30,  # Timeout razonable
                ping_interval=None,  # Desactivar ping para evitar conflictos
                ping_timeout=None,
                close_timeout=10,
            ) as ws:
                logger.info("✅ VibeVoice: WebSocket conectado, esperando mensajes...")
                first_chunk = True
                total_chunks = 0
                total_logs = 0
                timeout_seconds = 5  # Timeout más corto - si no hay chunks en 5s, fallar
                start_time = asyncio.get_event_loop().time()
                request_received_time = None
                backend_busy_received = False
                
                try:
                    while True:
                        # Verificar timeout
                        elapsed = asyncio.get_event_loop().time() - start_time
                        if elapsed > timeout_seconds:
                            logger.warning(f"⚠️ VibeVoice: Timeout después de {timeout_seconds}s sin recibir chunks")
                            break
                        
                        # Si recibimos backend_request_received pero no chunks después de 5s, asumir error
                        if request_received_time and total_chunks == 0:
                            elapsed_since_request = asyncio.get_event_loop().time() - request_received_time
                            if elapsed_since_request > 5:
                                logger.error(f"❌ VibeVoice: Sin chunks después de {elapsed_since_request:.1f}s desde backend_request_received")
                                break
                        
                        try:
                            # Esperar mensaje con timeout corto para poder verificar el timeout total
                            # Si recibimos backend_busy, salir inmediatamente
                            if backend_busy_received:
                                logger.warning("⚠️ VibeVoice: backend_busy recibido, fallando inmediatamente...")
                                await ws.close(code=1000, reason="Service busy")
                                raise RuntimeError("VibeVoice servidor ocupado (backend_busy recibido)")
                            
                            message = await asyncio.wait_for(ws.recv(), timeout=1.0)  # Timeout más corto
                        except asyncio.TimeoutError:
                            # Continuar el loop para verificar timeout total
                            continue
                        except websockets.exceptions.ConnectionClosed as e:
                            logger.warning(f"⚠️ VibeVoice: Conexión cerrada durante recv: code={e.code}, reason={e.reason}")
                            # Si es código 1013 (Service busy) o recibimos backend_busy, lanzar RuntimeError para retry
                            if e.code == 1013 or "busy" in str(e.reason).lower() or backend_busy_received:
                                raise RuntimeError(f"VibeVoice servidor ocupado (code={e.code}, reason={e.reason})")
                            if total_chunks == 0:
                                raise RuntimeError(f"VibeVoice cerró conexión sin enviar chunks (code={e.code}, reason={e.reason})")
                            break
                        # Mensajes de texto son logs/eventos
                        if isinstance(message, str):
                            total_logs += 1
                            logger.debug(f"📋 VibeVoice log #{total_logs}: {message[:200]}")
                            try:
                                log_data = json.loads(message)
                                if log_data.get("type") == "log":
                                    event = log_data.get("event", "")
                                    logger.info(f"📊 VibeVoice evento: {event}")
                                    
                                    if event == "backend_first_chunk_sent":
                                        logger.info("✅ VibeVoice: Primer chunk señalado por servidor")
                                    elif event == "backend_stream_complete":
                                        logger.info(f"✅ VibeVoice: Stream completado. Total chunks recibidos: {total_chunks}")
                                    elif event == "generation_error":
                                        error_msg = log_data.get("data", {}).get("message", "")
                                        logger.error(f"❌ VibeVoice error de generación: {error_msg}")
                                        raise RuntimeError(f"Error en generación: {error_msg}")
                                    elif event == "backend_request_received":
                                        if request_received_time is None:
                                            request_received_time = asyncio.get_event_loop().time()
                                            logger.info(f"✅ VibeVoice: Request recibido por servidor (tiempo: {request_received_time:.2f})")
                                        else:
                                            logger.info(f"✅ VibeVoice: Request recibido por servidor (duplicado)")
                                    elif event == "backend_busy":
                                        backend_busy_received = True
                                        logger.warning(f"⚠️ VibeVoice: Servidor ocupado (backend_busy) - fallando inmediatamente")
                                        # Si recibimos backend_busy, cerrar la conexión inmediatamente y fallar
                                        # No reintentar - usar Web Speech API directamente
                                        try:
                                            await ws.close(code=1000, reason="Service busy")
                                        except:
                                            pass
                                        raise RuntimeError("VibeVoice servidor ocupado (backend_busy recibido)")
                                    elif event == "client_disconnected":
                                        logger.warning("⚠️ VibeVoice: Cliente desconectado según servidor")
                                    else:
                                        logger.debug(f"📋 VibeVoice log: {event}")
                            except (json.JSONDecodeError, KeyError) as e:
                                logger.debug(f"⚠️ VibeVoice mensaje texto no JSON: {message[:100]} (error: {e})")
                            continue
                        
                        # Mensajes binarios son chunks PCM16
                        if isinstance(message, bytes):
                            total_chunks += 1
                            if first_chunk:
                                logger.info(f"🎵 VibeVoice: ✅ PRIMER CHUNK recibido: {len(message)} bytes")
                                first_chunk = False
                            if total_chunks % 10 == 0:
                                logger.info(f"📊 VibeVoice: {total_chunks} chunks recibidos hasta ahora")
                            yield message
                        else:
                            logger.warning(f"⚠️ VibeVoice: Tipo de mensaje desconocido: {type(message)}")
                    
                    logger.info(f"✅ VibeVoice: Loop terminado. Chunks: {total_chunks}, Logs: {total_logs}")
                    
                except websockets.exceptions.ConnectionClosed as e:
                    logger.warning(f"⚠️ VibeVoice: Conexión cerrada durante recepción: code={e.code}, reason={e.reason}")
                    logger.warning(f"⚠️ VibeVoice: Chunks recibidos antes del cierre: {total_chunks}")
                    if total_chunks == 0:
                        raise RuntimeError(f"VibeVoice cerró conexión sin enviar chunks (code={e.code}, reason={e.reason})")
                
                if total_chunks == 0:
                    logger.error("❌ VibeVoice: ERROR - No se recibieron chunks de audio")
                    raise RuntimeError("VibeVoice no envió ningún chunk de audio")
                else:
                    logger.info(f"✅ VibeVoice: Stream completado exitosamente con {total_chunks} chunks")
                    
        except websockets.exceptions.InvalidURI as e:
            logger.error(f"❌ VibeVoice: URL WebSocket inválida: {ws_url} - {e}")
            raise ValueError(f"URL WebSocket inválida: {ws_url}")
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"❌ VibeVoice: Conexión cerrada inmediatamente: code={e.code}, reason={e.reason}")
            raise RuntimeError(f"VibeVoice cerró conexión inmediatamente (code={e.code}, reason={e.reason})")
        except Exception as exc:
            logger.error(f"❌ VibeVoice: Error en WebSocket streaming: {exc}", exc_info=True)
            raise

    def synthesize_sync(self, text: str) -> bytes:
        """Wrapper sync que reutiliza la versión async."""
        import anyio
        chunks = []
        async def collect():
            async for chunk in self.synthesize_stream(text):
                chunks.append(chunk)
        anyio.run(collect)
        return b"".join(chunks)

    async def _synthesize_http(self, text: str) -> bytes:
        """
        Fallback HTTP: POST {base_url}/tts
        NOTA: VibeVoice no tiene endpoint HTTP, solo WebSocket.
        Este método devuelve silencio como fallback.
        """
        logger.warning("⚠️ VibeVoice: HTTP fallback no disponible (solo WebSocket)")
        # Devolver silencio PCM16 (1 segundo a 24kHz = 48000 samples = 96000 bytes)
        import struct
        silence_samples = 24000  # 1 segundo de silencio a 24kHz
        silence = struct.pack(f'<{silence_samples}h', *([0] * silence_samples))
        return silence


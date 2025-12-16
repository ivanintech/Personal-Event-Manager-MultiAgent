"""
WebSocket endpoint para voz bidireccional (STT + TTS) - VERSIÓN SIMPLIFICADA.

Basado en VibeVoice/demo/web/app.py para un flujo más simple y robusto.
"""

import logging
import json
import base64
import asyncio
import time
import io
import os
import sys
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from ..agents.graph import agent_orchestrator
from ..voice import get_tts_backend, get_stt_backend
from ..services.metrics import metrics_service

router = APIRouter(prefix="/api/v1", tags=["WebSocket"])
logger = logging.getLogger(__name__)
tts_backend = get_tts_backend()
stt_backend = get_stt_backend()

# Lock para evitar requests concurrentes (similar a VibeVoice)
_websocket_lock = asyncio.Lock()


def get_timestamp() -> str:
    """Timestamp formateado para logs."""
    return datetime.utcnow().isoformat() + "Z"


async def convert_webm_to_wav(webm_bytes: bytes) -> bytes:
    """
    Convierte audio WebM a WAV usando pydub (requiere ffmpeg).
    Si falla, intenta devolver el audio original o un WAV básico.
    """
    try:
        from pydub import AudioSegment
        from pydub.utils import which
        
        # Verificar que ffmpeg esté disponible
        ffmpeg_path = which("ffmpeg")
        if not ffmpeg_path:
            # Intentar buscar en rutas comunes de Windows
            if sys.platform == "win32":
                common_paths = [
                    r"C:\ffmpeg\bin\ffmpeg.exe",
                    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                    r"C:\tools\ffmpeg\bin\ffmpeg.exe",
                ]
                for path in common_paths:
                    if os.path.exists(path):
                        ffmpeg_path = path
                        # Configurar pydub para usar esta ruta
                        AudioSegment.converter = path
                        logger.info(f"✅ ffmpeg encontrado en: {path}")
                        break
            
            if not ffmpeg_path:
                logger.error("❌ ffmpeg no encontrado. Por favor instálalo:")
                logger.error("   Windows: choco install ffmpeg  o descarga de https://ffmpeg.org/download.html")
                logger.error("   Linux: sudo apt-get install ffmpeg")
                logger.error("   macOS: brew install ffmpeg")
                logger.warning("⚠️ Intentando usar audio sin conversión (puede fallar)...")
                # Intentar usar el audio directamente (algunos proveedores aceptan WebM)
                return webm_bytes
        
        # Cargar WebM desde bytes
        audio = AudioSegment.from_file(io.BytesIO(webm_bytes), format="webm")
        
        # Convertir a WAV: mono, 16kHz (estándar para Whisper)
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        
        # Exportar a WAV en memoria
        wav_buffer = io.BytesIO()
        audio.export(wav_buffer, format="wav")
        wav_bytes = wav_buffer.getvalue()
        
        logger.info(f"✅ WebM convertido a WAV: {len(webm_bytes)} bytes -> {len(wav_bytes)} bytes")
        return wav_bytes
        
    except ImportError:
        logger.warning("⚠️ pydub no instalado, intentando sin conversión...")
        # Intentar usar el audio directamente
        return webm_bytes
    except Exception as exc:
        logger.error(f"❌ Error convirtiendo WebM a WAV: {exc}", exc_info=True)
        # Fallback: intentar usar el audio original
        logger.warning("⚠️ Usando audio original sin conversión (puede fallar)")
        return webm_bytes


async def send_log_safe(ws: WebSocket, event: str, data: Optional[dict] = None) -> None:
    """Envía un log estructurado al cliente de forma segura (async)."""
    if ws.client_state != WebSocketState.CONNECTED:
        logger.debug(f"WebSocket no conectado, no se puede enviar log: {event}")
        return
    
    message = {
        "type": "log",
        "event": event,
        "data": data or {},
        "timestamp": get_timestamp(),
    }
    try:
        await ws.send_text(json.dumps(message))
        logger.debug(f"✅ Log enviado: {event}")
    except Exception as e:
        logger.debug(f"❌ Error enviando log {event}: {e}")


@router.websocket("/voice")
async def voice_stream(ws: WebSocket):
    """
    WebSocket simplificado para voz bidireccional.
    
    Flujo:
    1. Cliente se conecta → enviamos "backend_ready"
    2. Cliente envía mensaje (texto o audio) → procesamos
    3. Enviamos respuesta con audio en streaming
    4. Mantenemos conexión abierta para múltiples mensajes
    """
    await ws.accept()
    logger.info("🔵 WebSocket conectado")
    
    # Verificar si hay otro request en curso
    if _websocket_lock.locked():
        logger.warning("⚠️ Lock ocupado, rechazando conexión")
        try:
            await send_log_safe(ws, "backend_busy", {
                "message": "Por favor espera a que termine la otra petición."
            })
        except Exception:
            pass
        await ws.close(code=1013, reason="Service busy")
        return
    
    # Enviar mensaje de ready
    try:
        await send_log_safe(ws, "backend_ready", {"message": "Voice endpoint listo"})
        logger.info("✅ Backend ready enviado")
    except Exception as e:
        logger.error(f"❌ Error enviando ready: {e}")
        await ws.close()
        return
    
    # Flag para interrupciones
    current_task = None
    should_cancel = False
    
    try:
        while True:
            # Recibir mensaje del cliente
            try:
                msg_raw = await ws.receive_text()
                logger.info(f"📨 Mensaje recibido: {len(msg_raw)} bytes")
            except WebSocketDisconnect:
                logger.info("🔴 Cliente WS desconectado")
                break
            
            # Verificar si es una señal de interrupción o cancelación
            try:
                payload_check = json.loads(msg_raw)
                if payload_check.get("type") == "interrupt":
                    logger.warning("🛑 Interrupción recibida del cliente")
                    should_cancel = True
                    # Cancelar cualquier tarea en curso
                    if current_task and not current_task.done():
                        current_task.cancel()
                    continue
                elif payload_check.get("type") == "cancel":
                    logger.warning(f"❌ Cancelación recibida: {payload_check.get('reason', 'unknown')}")
                    should_cancel = True
                    if current_task and not current_task.done():
                        current_task.cancel()
                    # Enviar confirmación
                    await send_log_safe(ws, "request_cancelled", {
                        "reason": payload_check.get("reason", "unknown"),
                        "text": payload_check.get("text", "")
                    })
                    continue
            except (json.JSONDecodeError, KeyError):
                pass  # No es una señal de control, continuar procesamiento normal
            
            # Procesar mensaje con lock
            async with _websocket_lock:
                should_cancel = False  # Reset flag
                logger.info("🔒 Lock adquirido, procesando mensaje...")
                
                # Parsear payload
                try:
                    payload = json.loads(msg_raw)
                    logger.debug(f"📦 Payload parseado: {payload.keys()}")
                except json.JSONDecodeError:
                    payload = {"mode": "text", "text": msg_raw}
                    logger.debug("📝 Mensaje tratado como texto plano")

                mode = payload.get("mode", "text")
                user_text = None
                
                # Iniciar medición
                request_start_time = time.time()
                stt_duration = 0.0
                agent_duration = 0.0
                tts_duration = 0.0
                first_chunk_latency = None
                
                # ===== STT =====
                if mode == "audio":
                    logger.info("🎤 Modo audio - iniciando STT...")
                    stt_start_time = time.time()
                    await send_log_safe(ws, "stt_started")
                    
                    b64 = payload.get("audio_base64", "")
                    logger.info(f"📊 Audio base64 recibido: {len(b64)} caracteres")
                    
                    if not b64:
                        logger.error("❌ Audio base64 vacío - verificar que el frontend está enviando audio")
                        await send_log_safe(ws, "stt_error", {"error": "Audio base64 vacío"})
                        continue
                    
                    try:
                        audio_bytes = base64.b64decode(b64)
                        logger.info(f"🔊 Audio decodificado: {len(audio_bytes)} bytes")
                        
                        if len(audio_bytes) == 0:
                            logger.error("❌ Audio decodificado está vacío")
                            await send_log_safe(ws, "stt_error", {"error": "Audio vacío después de decodificar"})
                            continue
                        
                        # Convertir WebM a WAV si es necesario (Groq/OpenAI Whisper espera WAV)
                        logger.info("🔄 Convirtiendo WebM a WAV...")
                        await send_log_safe(ws, "audio_conversion_started", {
                            "format": "WebM to WAV",
                            "input_size_bytes": len(audio_bytes)
                        })
                        conversion_start = time.time()
                        audio_bytes_wav = await convert_webm_to_wav(audio_bytes)
                        conversion_duration = (time.time() - conversion_start) * 1000
                        logger.info(f"🎵 Audio convertido a WAV: {len(audio_bytes_wav)} bytes")
                        await send_log_safe(ws, "audio_conversion_completed", {
                            "output_size_bytes": len(audio_bytes_wav),
                            "duration_ms": round(conversion_duration, 2),
                            "compression_ratio": f"{(len(audio_bytes)/len(audio_bytes_wav) if len(audio_bytes_wav) > 0 else 1):.2f}x"
                        })
                        
                        if len(audio_bytes_wav) == 0:
                            logger.error("❌ Audio WAV convertido está vacío")
                            await send_log_safe(ws, "stt_error", {"error": "Error en conversión de audio"})
                            continue
                        
                        logger.info(f"🎤 Enviando audio a STT (Groq/OpenAI)...")
                        await send_log_safe(ws, "stt_processing_started", {
                            "provider": "Groq",
                            "model": "whisper-large-v3",
                            "audio_size_bytes": len(audio_bytes_wav),
                            "estimated_duration_sec": len(audio_bytes_wav) / 16000  # Aproximado
                        })
                        user_text = stt_backend.transcribe_sync(audio_bytes_wav)
                        stt_duration = (time.time() - stt_start_time) * 1000
                        metrics_service.record_voice_stt(stt_duration)
                        
                        logger.info(f"✅ STT completado: '{user_text}' ({stt_duration:.2f}ms)")
                        # Enviar inmediatamente para que el usuario vea que fue escuchado
                        await send_log_safe(ws, "stt_completed", {
                            "text": user_text,
                            "text_length": len(user_text) if user_text else 0,
                            "duration_ms": round(stt_duration, 2)
                        })
                        # Pequeño delay para asegurar que el mensaje se muestra antes de procesar
                        await asyncio.sleep(0.1)
                    except Exception as exc:
                        logger.error(f"❌ Error en STT: {exc}", exc_info=True)
                        stt_duration = (time.time() - stt_start_time) * 1000
                        metrics_service.record_voice_stt(stt_duration, success=False)
                        await send_log_safe(ws, "stt_error", {"error": str(exc)})
                        continue
                else:
                    user_text = payload.get("text", msg_raw)
                    logger.info(f"📝 Modo texto: '{user_text}'")
                
                if not user_text or not user_text.strip():
                    logger.warning("⚠️ Query vacío")
                    await send_log_safe(ws, "empty_query")
                    continue
                
                # Validación rápida del mensaje (similar a frontend)
                user_text_trimmed = user_text.strip()
                if len(user_text_trimmed) < 2:
                    logger.warning("⚠️ Mensaje muy corto, ignorando")
                    await send_log_safe(ws, "message_too_short", {
                        "text": user_text_trimmed,
                        "reason": "Mensaje muy corto o sin sentido"
                    })
                    continue
                
                # Verificar si hay letras (no solo números o caracteres especiales)
                import re
                has_letters = bool(re.search(r'[a-zA-ZáéíóúñüÁÉÍÓÚÑÜ]', user_text_trimmed))
                if not has_letters and len(user_text_trimmed) < 5:
                    logger.warning("⚠️ Mensaje sin letras, probablemente ruido")
                    await send_log_safe(ws, "message_no_sense", {
                        "text": user_text_trimmed,
                        "reason": "Mensaje sin letras, probablemente ruido"
                    })
                    continue
                
                # ===== AGENT =====
                logger.info(f"🤖 Procesando con agente: '{user_text[:50]}...'")
                agent_start_time = time.time()
                await send_log_safe(ws, "agent_processing_started", {
                    "query_length": len(user_text)
                })
                
                try:
                    # Callback para enviar logs del agente al frontend (síncrono para evitar warnings)
                    def agent_log_callback(event: str, data: dict):
                        # Verificar si hay interrupción antes de enviar log
                        if should_cancel:
                            return
                        # Crear tarea asyncio para enviar el log sin bloquear
                        asyncio.create_task(send_log_safe(ws, f"agent_{event}", data))
                    
                    # Verificar interrupción antes de procesar
                    if should_cancel:
                        logger.warning("🛑 Procesamiento cancelado por interrupción")
                        await send_log_safe(ws, "request_cancelled", {
                            "reason": "interrupted_by_user"
                        })
                        continue
                    
                    # Pasar callback al orchestrator
                    result = await agent_orchestrator.run(
                        query=user_text,
                        log_callback=agent_log_callback
                    )
                    
                    # Verificar interrupción después de procesar
                    if should_cancel:
                        logger.warning("🛑 Procesamiento cancelado después de agente")
                        await send_log_safe(ws, "request_cancelled", {
                            "reason": "interrupted_after_agent"
                        })
                        continue
                    
                    text_reply = result.get("text", "Sin respuesta.")
                    agent_duration = (time.time() - agent_start_time) * 1000
                    metrics_service.record_voice_agent(agent_duration)
                    
                    logger.info(f"✅ Agente respondió: '{text_reply[:50]}...' ({agent_duration:.2f}ms)")
                    await send_log_safe(ws, "agent_response_text", {"text": text_reply})
                    await send_log_safe(ws, "agent_processing_completed", {
                        "response_length": len(text_reply),
                        "duration_ms": round(agent_duration, 2),
                        "tools_used": [t.get("tool_name") for t in result.get("tool_calls", [])],
                        "iterations": result.get("debug", {}).get("iterations", 0)
                    })
                except Exception as exc:
                    logger.error(f"❌ Error en agente: {exc}", exc_info=True)
                    agent_duration = (time.time() - agent_start_time) * 1000
                    metrics_service.record_voice_agent(agent_duration, success=False)
                    await send_log_safe(ws, "agent_error", {"error": str(exc)})
                    text_reply = f"Error procesando la consulta: {exc}"
                
                # ===== TTS =====
                logger.info(f"🔊 Iniciando TTS para texto de {len(text_reply)} caracteres")
                tts_start_time = time.time()
                await send_log_safe(ws, "tts_started", {"text_length": len(text_reply)})
                
                first_chunk = True
                chunk_count = 0
                tts_timeout = 3.0  # Timeout de 3 segundos para TTS - si no hay chunks, usar Web Speech API
                tts_start = time.time()
                
                try:
                    logger.info(f"🎵 Conectando a VibeVoice para sintetizar audio...")
                    async for audio_chunk in tts_backend.synthesize_stream(text_reply):
                        # Verificar timeout - si pasan 3 segundos sin chunks, activar fallback
                        elapsed = time.time() - tts_start
                        if elapsed > tts_timeout and chunk_count == 0:
                            logger.warning(f"⚠️ Timeout de TTS ({tts_timeout}s) sin chunks - activando Web Speech API")
                            break
                        if ws.client_state != WebSocketState.CONNECTED:
                            logger.warning("⚠️ WebSocket desconectado durante streaming")
                            break
                        
                        if not audio_chunk or len(audio_chunk) == 0:
                            logger.warning("⚠️ Chunk de audio vacío, saltando...")
                            continue
                        
                        # Verificar que el chunk sea válido (múltiplo de 2 bytes para PCM16)
                        if len(audio_chunk) % 2 != 0:
                            logger.warning(f"⚠️ Chunk de audio con tamaño impar ({len(audio_chunk)} bytes), recortando...")
                            audio_chunk = audio_chunk[:len(audio_chunk) - 1]
                            if len(audio_chunk) == 0:
                                logger.warning("⚠️ Chunk vacío después del recorte, saltando...")
                                continue
                        
                        # Verificar que sea realmente audio PCM16 (no texto de error)
                        # Los chunks de audio PCM16 deberían tener variación en los bytes
                        # Si todos los bytes son iguales o muy similares, puede ser texto
                        if len(audio_chunk) < 4:
                            logger.warning(f"⚠️ Chunk demasiado pequeño ({len(audio_chunk)} bytes), saltando...")
                            continue
                        
                        # Enviar chunk
                        await ws.send_bytes(audio_chunk)
                        chunk_count += 1
                        
                        if first_chunk:
                            first_chunk_time = time.time()
                            first_chunk_latency = (first_chunk_time - tts_start_time) * 1000
                            logger.info(f"✅ Primer chunk enviado: {len(audio_chunk)} bytes, latencia: {first_chunk_latency:.2f}ms")
                            await send_log_safe(ws, "tts_first_chunk_sent", {
                                "first_chunk_latency_ms": round(first_chunk_latency, 2),
                                "chunk_size_bytes": len(audio_chunk)
                            })
                            first_chunk = False
                        
                        if chunk_count % 10 == 0:
                            logger.debug(f"📊 Enviados {chunk_count} chunks hasta ahora")
                    
                    tts_duration = (time.time() - tts_start_time) * 1000
                    metrics_service.record_voice_tts(tts_duration, first_chunk_latency_ms=first_chunk_latency)
                    
                    logger.info(f"✅ TTS completado: {chunk_count} chunks, {tts_duration:.2f}ms")
                    await send_log_safe(ws, "tts_completed", {
                        "chunks_sent": chunk_count,
                        "duration_ms": round(tts_duration, 2),
                        "first_chunk_latency_ms": round(first_chunk_latency, 2) if first_chunk_latency else None,
                        "fallback_needed": chunk_count == 0,
                        "fallback_available": chunk_count == 0
                    })
                    
                    if chunk_count == 0:
                        logger.warning("⚠️ No se recibieron chunks de audio de VibeVoice - activando Web Speech API")
                        # Enviar evento tts_error para que el frontend active Web Speech API inmediatamente
                        await send_log_safe(ws, "tts_error", {
                            "error": "No se recibieron chunks de audio del servidor TTS. VibeVoice puede estar teniendo problemas procesando el texto.",
                            "fallback_available": True,
                            "message": "El frontend usará Web Speech API como fallback.",
                            "chunks_received": 0,
                            "use_web_speech": True  # Señal explícita para el frontend
                        })
                        # También enviar tts_completed con 0 chunks para que el frontend lo detecte
                        await send_log_safe(ws, "tts_completed", {
                            "chunks_sent": 0,
                            "duration_ms": round(tts_duration, 2),
                            "fallback_needed": True
                        })
                        # No lanzar excepción aquí, solo loguear el error
                        # El frontend debe usar Web Speech API como fallback
                        
                except Exception as exc:
                    logger.error(f"❌ Error en TTS streaming: {exc}", exc_info=True)
                    tts_duration = (time.time() - tts_start_time) * 1000
                    metrics_service.record_voice_tts(tts_duration, success=False)
                    await send_log_safe(ws, "tts_error", {
                        "error": str(exc),
                        "fallback_available": True,
                        "message": "El frontend usará Web Speech API como fallback."
                    })
                
                # ===== FINALIZACIÓN =====
                total_duration = (time.time() - request_start_time) * 1000
                metrics_service.record_voice_request(total_duration)
                
                logger.info(f"✅ Request completado: {total_duration:.2f}ms total")
                await send_log_safe(ws, "request_completed", {
                    "total_duration_ms": round(total_duration, 2),
                    "stt_duration_ms": round(stt_duration, 2),
                    "agent_duration_ms": round(agent_duration, 2),
                    "tts_duration_ms": round(tts_duration, 2),
                    "first_chunk_latency_ms": round(first_chunk_latency, 2) if first_chunk_latency else None
                })
                
                # Señal de finalización
                if ws.client_state == WebSocketState.CONNECTED:
                    try:
                        await ws.send_text(json.dumps({"type": "complete"}))
                        logger.debug("✅ Señal 'complete' enviada")
                    except Exception as e:
                        logger.debug(f"❌ Error enviando 'complete': {e}")
                
                logger.info("🔓 Lock liberado, esperando siguiente mensaje...")
                
    except WebSocketDisconnect:
        logger.info("🔴 Cliente WS desconectado durante procesamiento")
    except Exception as exc:
        logger.error(f"❌ Error en WS voz: {exc}", exc_info=True)
        if ws.client_state == WebSocketState.CONNECTED:
            try:
                await send_log_safe(ws, "backend_error", {"error": str(exc)})
            except Exception:
                pass
    finally:
        logger.info("🔴 Cerrando WebSocket...")
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.close()
        except Exception:
            pass

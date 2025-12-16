# Mejoras de Voz - Integración con VibeVoice

## Resumen de Mejoras Implementadas

Basado en el código de referencia de `VibeVoice/demo/web/`, se han implementado las siguientes mejoras:

### 1. Streaming WebSocket Real para VibeVoice ✅

**Archivo**: `app/voice/vibevoice.py`

**Mejoras**:
- ✅ Streaming real vía WebSocket (`/stream`) en lugar de HTTP POST
- ✅ Recibe chunks PCM16 en tiempo real
- ✅ Manejo de logs estructurados del servidor VibeVoice
- ✅ Fallback automático a HTTP si WebSocket falla
- ✅ Mejor manejo de errores y reconexión

**Antes**:
```python
# Solo HTTP POST, un solo chunk
resp = await client.post(f"{base_url}/tts", json=payload)
return resp.content
```

**Ahora**:
```python
# WebSocket streaming con chunks en tiempo real
async with websockets.connect(ws_url) as ws:
    async for message in ws:
        if isinstance(message, bytes):
            yield message  # Chunk PCM16
```

### 2. WebSocket Voice Endpoint Mejorado ✅

**Archivo**: `app/api/ws.py`

**Mejoras**:
- ✅ Logs estructurados para debugging (`{"type": "log", "event": "...", "data": {...}}`)
- ✅ Lock para evitar requests concurrentes (similar a VibeVoice)
- ✅ Mejor manejo de estados (STT started/completed, TTS started/first_chunk/completed)
- ✅ Streaming de audio en tiempo real
- ✅ Manejo robusto de errores y desconexiones
- ✅ Timestamps en logs

**Eventos de log soportados**:
- `backend_ready`: Servidor listo
- `stt_started` / `stt_completed` / `stt_error`: Proceso de transcripción
- `agent_processing_started` / `agent_processing_completed` / `agent_error`: Procesamiento del agente
- `tts_started` / `tts_first_chunk_sent` / `tts_completed` / `tts_error`: Generación de audio
- `backend_busy`: Otro request en curso
- `client_disconnected`: Cliente desconectado
- `backend_error`: Error general

### 3. Protocolo Mejorado

**Mensajes del Cliente**:
```json
// Modo texto
{"mode": "text", "text": "Hola, ¿qué puedes hacer?"}

// Modo audio (STT)
{"mode": "audio", "audio_base64": "..."}
```

**Mensajes del Servidor**:
```json
// Logs estructurados
{
  "type": "log",
  "event": "tts_first_chunk_sent",
  "data": {},
  "timestamp": "2025-12-15T12:00:00Z"
}

// Finalización
{"type": "complete"}

// Error
{"type": "error", "message": "..."}

// Chunks de audio: bytes (PCM16)
```

## Comparación con VibeVoice Demo

| Característica | VibeVoice Demo | Nuestra Implementación |
|---------------|----------------|------------------------|
| WebSocket streaming | ✅ | ✅ |
| Logs estructurados | ✅ | ✅ |
| Lock concurrente | ✅ | ✅ |
| Chunks PCM16 | ✅ | ✅ |
| Manejo de errores | ✅ | ✅ |
| STT integrado | ❌ | ✅ |
| Agente integrado | ❌ | ✅ |

## Próximos Pasos (Opcionales)

1. **Streaming bidireccional completo**: Permitir que el cliente envíe audio mientras recibe TTS
2. **Interrupción de TTS**: Permitir cancelar generación si el usuario habla de nuevo
3. **Métricas de latencia**: Medir tiempo de STT, procesamiento, y TTS
4. **UI mejorada**: Integrar logs en la interfaz web para debugging

## Uso

### Configuración

```env
VOICE_TTS_BACKEND=vibevoice
VIBEVOICE_BASE_URL=http://localhost:8001
VIBEVOICE_MODEL=VibeVoice-Realtime-0.5B
```

### Ejemplo de Cliente WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/voice');
ws.binaryType = 'arraybuffer';

// Enviar texto
ws.send(JSON.stringify({mode: 'text', text: 'Hola'}));

// Recibir logs
ws.onmessage = (event) => {
  if (typeof event.data === 'string') {
    const msg = JSON.parse(event.data);
    if (msg.type === 'log') {
      console.log(`[${msg.event}]`, msg.data);
    }
  } else {
    // Chunk de audio PCM16
    const audioChunk = new Int16Array(event.data);
    // Reproducir audio...
  }
};
```

## Dependencias Añadidas

- `websockets>=12.0`: Para conexión WebSocket con VibeVoice


"""
Servicio para iniciar VibeVoice automáticamente como subproceso.
Se ejecuta cuando el servidor principal inicia si VOICE_TTS_BACKEND=vibevoice.
"""

import os
import sys
import subprocess
import logging
import time
import signal
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Ruta base del proyecto
# app/services/vibevoice_launcher.py -> app -> Proyecto/personal-coordination-voice-agent
PROJECT_ROOT = Path(__file__).parent.parent.parent
# Proyecto/personal-coordination-voice-agent -> Proyecto -> VibeVoice
VIBEVOICE_DIR = PROJECT_ROOT.parent / "VibeVoice"
VIBEVOICE_DEMO_SCRIPT = VIBEVOICE_DIR / "demo" / "vibevoice_realtime_demo.py"

# Proceso de VibeVoice
_vibevoice_process: Optional[subprocess.Popen] = None


def start_vibevoice(
    model_path: Optional[str] = None,
    port: int = 8001,
    device: str = "cpu"
) -> bool:
    """
    Inicia VibeVoice como subproceso.
    
    Args:
        model_path: Ruta al modelo (si None, usa el modelo por defecto de HuggingFace)
        port: Puerto donde escuchará VibeVoice (default: 8001)
        device: Dispositivo a usar (cpu, cuda, mps)
    
    Returns:
        True si se inició correctamente, False en caso contrario
    """
    global _vibevoice_process
    
    if _vibevoice_process is not None:
        logger.warning("VibeVoice ya está corriendo")
        return True
    
    if not VIBEVOICE_DIR.exists():
        logger.error(f"Directorio de VibeVoice no encontrado: {VIBEVOICE_DIR}")
        return False
    
    if not VIBEVOICE_DEMO_SCRIPT.exists():
        logger.error(f"Script de VibeVoice no encontrado: {VIBEVOICE_DEMO_SCRIPT}")
        return False
    
    # Determinar el modelo por defecto si no se especifica
    if not model_path:
        # Modelo por defecto de HuggingFace
        model_path = "microsoft/VibeVoice-Realtime-0.5B"
        logger.info(f"Usando modelo por defecto: {model_path}")
    
    # Determinar el ejecutable de Python
    python_exe = sys.executable
    
    # Verificar si hay un venv en VibeVoice
    vibevoice_venv_python = VIBEVOICE_DIR / ".venv" / "Scripts" / "python.exe"
    if sys.platform != "win32":
        vibevoice_venv_python = VIBEVOICE_DIR / ".venv" / "bin" / "python"
    
    if vibevoice_venv_python.exists():
        python_exe = str(vibevoice_venv_python)
        logger.info(f"Usando Python de VibeVoice venv: {python_exe}")
    else:
        logger.info(f"Usando Python del sistema: {python_exe}")
    
    # Construir comando
    cmd = [
        python_exe,
        str(VIBEVOICE_DEMO_SCRIPT),
        "--model_path", model_path,
        "--port", str(port),
        "--device", device
    ]
    
    logger.info(f"Iniciando VibeVoice con comando: {' '.join(cmd)}")
    
    try:
        # Iniciar proceso en background
        _vibevoice_process = subprocess.Popen(
            cmd,
            cwd=str(VIBEVOICE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        
        # Esperar un poco para ver si inicia correctamente
        time.sleep(3)
        
        # Verificar si el proceso sigue corriendo
        if _vibevoice_process.poll() is not None:
            # El proceso terminó, leer stderr para ver el error
            _, stderr = _vibevoice_process.communicate()
            logger.error(f"VibeVoice falló al iniciar: {stderr}")
            _vibevoice_process = None
            return False
        
        logger.info(f"✅ VibeVoice iniciado en puerto {port} (PID: {_vibevoice_process.pid})")
        
        # Esperar un poco más para que el servidor esté listo
        time.sleep(2)
        
        return True
        
    except Exception as e:
        logger.error(f"Error iniciando VibeVoice: {e}", exc_info=True)
        _vibevoice_process = None
        return False


def stop_vibevoice() -> bool:
    """
    Detiene el proceso de VibeVoice.
    
    Returns:
        True si se detuvo correctamente, False en caso contrario
    """
    global _vibevoice_process
    
    if _vibevoice_process is None:
        return True
    
    try:
        logger.info(f"Deteniendo VibeVoice (PID: {_vibevoice_process.pid})")
        
        # Enviar señal de terminación
        if sys.platform == "win32":
            _vibevoice_process.terminate()
        else:
            _vibevoice_process.send_signal(signal.SIGTERM)
        
        # Esperar hasta 5 segundos para que termine
        try:
            _vibevoice_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Forzar terminación si no responde
            logger.warning("VibeVoice no respondió a SIGTERM, forzando terminación")
            _vibevoice_process.kill()
            _vibevoice_process.wait()
        
        logger.info("✅ VibeVoice detenido")
        _vibevoice_process = None
        return True
        
    except Exception as e:
        logger.error(f"Error deteniendo VibeVoice: {e}", exc_info=True)
        _vibevoice_process = None
        return False


def is_vibevoice_running() -> bool:
    """Verifica si VibeVoice está corriendo."""
    global _vibevoice_process
    
    if _vibevoice_process is None:
        return False
    
    return _vibevoice_process.poll() is None


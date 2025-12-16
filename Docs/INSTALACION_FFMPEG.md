# Instalación de FFmpeg

FFmpeg es necesario para convertir audio WebM a WAV para el procesamiento de STT (Speech-to-Text).

## Windows

### Opción 1: Chocolatey (Recomendado)
```powershell
choco install ffmpeg
```

### Opción 2: Descarga Manual
1. Descarga FFmpeg desde: https://ffmpeg.org/download.html
2. Extrae el archivo ZIP
3. Agrega la carpeta `bin` al PATH del sistema:
   - Busca "Variables de entorno" en Windows
   - Edita la variable PATH
   - Agrega la ruta completa a la carpeta `bin` (ej: `C:\ffmpeg\bin`)

### Opción 3: Scoop
```powershell
scoop install ffmpeg
```

## Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

## macOS
```bash
brew install ffmpeg
```

## Verificar Instalación

Después de instalar, verifica que ffmpeg esté disponible:

```bash
ffmpeg -version
```

Si el comando funciona, ffmpeg está correctamente instalado.

## Nota

Si ffmpeg no está instalado, el sistema intentará usar el audio WebM directamente, pero esto puede fallar con algunos proveedores de STT que requieren WAV.



"""
Script simple para iniciar el servidor FastAPI.
Útil para debugging y ver errores en tiempo real.
"""

import uvicorn
import sys
import os

# Añadir el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("🚀 Iniciando servidor FastAPI...")
    print("📍 URL: http://127.0.0.1:8000")
    print("📄 Frontend: http://127.0.0.1:8000/static/events.html")
    print("📚 API Docs: http://127.0.0.1:8000/docs")
    print("\n⏳ Espera a que aparezca 'Application startup complete'...\n")
    
    try:
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\n👋 Servidor detenido")
    except Exception as e:
        print(f"\n❌ Error al iniciar servidor: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)





"""
Script de diagnóstico para verificar que el servidor puede iniciar correctamente.
Ejecuta este script para ver errores específicos.
"""

import sys
import os
import asyncio
import traceback

# Añadir el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Verificando configuracion...\n")

try:
    # 1. Verificar .env
    from dotenv import load_dotenv
    load_dotenv()
    print("[OK] .env cargado")
    
    # 2. Verificar variables críticas
    supabase_url = os.getenv('SUPABASE_URL')
    nebius_key = os.getenv('NEBIUS_API_KEY')
    
    if not supabase_url:
        print("[ERROR] SUPABASE_URL no encontrado")
    else:
        print(f"[OK] SUPABASE_URL: {supabase_url[:30]}...")
    
    if not nebius_key:
        print("[ERROR] NEBIUS_API_KEY no encontrado")
    else:
        print(f"[OK] NEBIUS_API_KEY: {nebius_key[:30]}...")
    
    # 3. Intentar importar settings
    print("\n[INFO] Importando configuracion...")
    from app.config.settings import get_settings
    settings = get_settings()
    print(f"[OK] Settings cargado - AI Provider: {settings.ai_provider}")
    
    # 4. Intentar importar app
    print("\n[INFO] Importando aplicacion...")
    from app.main import app
    print("[OK] App importada correctamente")
    
    # 5. Verificar base de datos (sin conectar)
    print("\n[INFO] Verificando modulos de base de datos...")
    from app.config.database import db
    print("[OK] Database module importado")
    
    print("\n" + "="*50)
    print("[OK] TODAS LAS VERIFICACIONES PASARON")
    print("="*50)
    print("\n[INFO] El servidor deberia poder iniciar correctamente.")
    print("[INFO] Ejecuta: python start_server.py")
    print("       O: python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000\n")
    
except Exception as e:
    print("\n" + "="*50)
    print("[ERROR] ERROR ENCONTRADO")
    print("="*50)
    print(f"\nError: {e}")
    print("\nTraceback completo:")
    traceback.print_exc()
    sys.exit(1)


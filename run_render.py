#!/usr/bin/env python3
"""
Script de démarrage Render : affiche les erreurs complètes avant de quitter.
Utilisez ce script comme startCommand pour voir la traceback en cas de crash.
"""
import os
import sys

def main():
    port = os.environ.get("PORT", "5000")
    print(f"[run_render] Démarrage sur le port {port}")
    print(f"[run_render] DATABASE_URL présent: {bool(os.environ.get('DATABASE_URL'))}")
    print(f"[run_render] SUPABASE_URL présent: {bool(os.environ.get('SUPABASE_URL'))}")
    
    try:
        import uvicorn
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=int(port),
            log_level="info"
        )
    except Exception as e:
        print(f"\n❌ ERREUR AU DÉMARRAGE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

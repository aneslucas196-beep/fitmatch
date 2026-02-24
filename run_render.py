#!/usr/bin/env python3
"""
Script de démarrage Render : affiche les erreurs complètes avant de quitter.
Utilisez ce script comme startCommand pour voir la traceback en cas de crash.
"""
import os
import sys

def main():
    port = os.environ.get("PORT", "5000")
    from logger import get_logger
    log = get_logger()
    log.info(f"[run_render] Démarrage sur le port {port}")
    log.info(f"[run_render] DATABASE_URL présent: {bool(os.environ.get('DATABASE_URL'))}")
    log.info(f"[run_render] SUPABASE_URL présent: {bool(os.environ.get('SUPABASE_URL'))}")
    
    try:
        import uvicorn
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=int(port),
            log_level="info"
        )
    except Exception as e:
        log.error(f"ERREUR AU DÉMARRAGE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

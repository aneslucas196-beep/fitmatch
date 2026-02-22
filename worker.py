#!/usr/bin/env python3
"""
Worker H24 pour les rappels FitMatch.
Tourne en boucle, appelle process_due_reminders() régulièrement.
À déployer sur Render (Background Worker) ou tout serveur persistant.
Ne dépend pas de FastAPI/Vercel.
"""
import os
import time
from datetime import datetime

# Intervalle entre deux exécutions (secondes). 60 = 1 min, 300 = 5 min
INTERVAL_SEC = int(os.environ.get("REMINDERS_INTERVAL_SEC", "60"))

def main():
    # Import ici pour que les variables d'env soient lues au démarrage
    from main import process_due_reminders

    print(f"[Worker] Démarrage – intervalle {INTERVAL_SEC}s. Ctrl+C pour arrêter.")
    while True:
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        try:
            print(f"[{ts}] Running process_due_reminders()...")
            result = process_due_reminders()
            print(f"[{ts}] Done – rappels envoyés: {result}")
        except Exception as e:
            print(f"[{ts}] Error: {e}")
            import traceback
            traceback.print_exc()
        time.sleep(INTERVAL_SEC)

if __name__ == "__main__":
    main()

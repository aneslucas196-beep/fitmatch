#!/bin/bash
# Arrête le serveur lancé avec ./start.sh --bg
cd "$(dirname "$0")"
if [ -f fitmatch.pid ]; then
  kill "$(cat fitmatch.pid)" 2>/dev/null && echo "Serveur arrêté." || echo "PID invalide ou déjà arrêté."
  rm -f fitmatch.pid
else
  echo "Aucun fitmatch.pid trouvé. Le serveur n'était peut-être pas lancé avec --bg."
fi

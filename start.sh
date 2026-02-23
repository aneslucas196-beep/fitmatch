#!/bin/bash
# Lance FitMatch (web + rappels 24/7)
# Usage: ./start.sh          → lance en premier plan
#        ./start.sh --bg     → lance en arrière-plan (nohup)
cd "$(dirname "$0")"
export PORT="${PORT:-5000}"
if [ "$1" = "--bg" ]; then
  nohup python3 start_server.py > fitmatch.log 2>&1 &
  echo $! > fitmatch.pid
  echo "Serveur démarré en arrière-plan (PID $(cat fitmatch.pid)). Log: fitmatch.log"
else
  python3 start_server.py
fi

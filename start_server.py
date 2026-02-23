#!/usr/bin/env python3
"""
Lance le serveur FitMatch (web + rappels 24/7).
Une seule commande : le site tourne ET les rappels/emails partent automatiquement.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(__import__("os").environ.get("PORT", "5000")),
        reload=False,
    )

"""
Routes d'authentification : login API, logout.
Les dépendances sont injectées par main.py.
"""
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse


def register_auth_routes(app, deps: dict):
    """Enregistre les routes auth sur l'app."""
    get_demo_user = deps["get_demo_user"]
    verify_password = deps["verify_password"]
    log = deps.get("log")
    limiter = deps.get("limiter")

    async def _api_login(request: Request):
        """API de connexion pour JavaScript (JSON)."""
        try:
            data = await request.json()
            email = data.get("email", "").lower().strip()
            password = data.get("password", "")

            if not email or not password:
                raise HTTPException(status_code=400, detail="Email et mot de passe requis")

            cached_user = get_demo_user(email)
            if cached_user:
                stored_password = cached_user.get("password", "").strip()
                if stored_password and verify_password(password.strip(), stored_password):
                    if log:
                        log.info("✅ API Login: compte trouvé")
                    return {
                        "success": True,
                        "full_name": cached_user.get("full_name", email.split("@")[0]),
                        "email": email,
                        "role": cached_user.get("role", "client"),
                    }

            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

        except HTTPException:
            raise
        except Exception as e:
            if log:
                log.error(f"Erreur API login: {e}")
            raise HTTPException(status_code=500, detail="Erreur serveur")

    api_login_handler = limiter.limit("10/minute")(_api_login) if limiter else _api_login
    app.add_api_route("/api/login", api_login_handler, methods=["POST"], tags=["auth"])

    @app.get("/logout")
    async def logout():
        """Déconnexion."""
        response = RedirectResponse(url="/", status_code=303)
        response.delete_cookie("session_token")
        return response

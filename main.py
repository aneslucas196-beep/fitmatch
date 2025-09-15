from fastapi import FastAPI, Request, Form, HTTPException, Depends, File, UploadFile, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional, List
import uvicorn
import jwt
import os
import uuid
from datetime import datetime, timedelta

from utils import (
    geocode_city, 
    search_coaches_mock, 
    get_coach_by_id_mock, 
    get_transformations_by_coach_mock,
    get_supabase_anon_client,
    get_supabase_client_for_user,
    # Nouvelles fonctions Supabase
    sign_up_user,
    sign_in_user,
    get_user_profile,
    search_coaches_supabase,
    get_coach_by_id_supabase,
    get_transformations_by_coach_supabase,
    update_coach_profile,
    update_coach_specialties,
    add_transformation,
    upload_transformation_images
)

app = FastAPI()

# Exception handler pour rediriger automatiquement les utilisateurs non connectés
@app.exception_handler(401)
async def auth_exception_handler(request: Request, exc: HTTPException):
    """Redirige automatiquement vers /login si utilisateur non connecté."""
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=303)
    return exc

# Configuration des templates et fichiers statiques
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Client Supabase anonyme (si disponible)
supabase_anon = get_supabase_anon_client()

# Fonction de validation du mot de passe
def is_valid_password(password: str) -> bool:
    """Valide qu'un mot de passe respecte les critères de sécurité.
    
    Critères: Au moins 8 caractères, une lettre et un chiffre.
    """
    import re
    # Au moins 8 caractères, une lettre et un chiffre
    return bool(re.match(r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$', password))

# Helper functions pour l'authentification
def get_current_user(session_token: Optional[str] = Cookie(None)):
    """Récupère l'utilisateur connecté via le token de session."""
    # Validation des prérequis
    if not session_token:
        return None
    
    # Validation du format du token
    if not isinstance(session_token, str) or len(session_token.strip()) < 10:
        print("❌ Token de session invalide (format)")
        return None
    
    # Mode démo si pas de Supabase
    if not supabase_anon:
        if session_token == "demo_token":
            return {
                "id": "demo_user", 
                "email": "demo@example.com", 
                "role": "coach",
                "full_name": "Utilisateur Démo",
                "_access_token": session_token
            }
        return None
    
    try:
        import os
        
        # Décoder le JWT pour récupérer l'ID utilisateur (plus robuste que auth.get_user)
        # On ne vérifie pas la signature car Supabase l'a déjà fait
        decoded_token = jwt.decode(session_token, options={"verify_signature": False})
        user_id = decoded_token.get("sub")
        
        if not user_id:
            print("❌ Token JWT invalide (pas d'ID utilisateur)")
            return None
            
        # Créer un client authentifié pour respecter les politiques RLS
        user_supabase = get_supabase_client_for_user(session_token)
        if not user_supabase:
            print("❌ Impossible de créer le client authentifié")
            return None
            
        # Charger le profil directement depuis la table profiles
        profile = get_user_profile(user_supabase, user_id)
        if profile:
            profile["_access_token"] = session_token  # Garder le token pour les futures requêtes
            print(f"✅ Utilisateur authentifié: {profile.get('email', 'N/A')}")
            return profile
        else:
            # Profil non trouvé - créer automatiquement lors de la première connexion
            print(f"⚠️ Profil manquant pour utilisateur {user_id}, création automatique")
            
            # Récupérer l'email depuis le token JWT
            user_email = decoded_token.get("email")
            if not user_email:
                print("❌ Email non trouvé dans le token")
                return None
                
            # Créer un objet utilisateur mock pour la création de profil
            mock_user = type('User', (), {
                'id': user_id,
                'email': user_email,
                'user_metadata': {}
            })()
            
            return create_profile_on_first_login(user_supabase, mock_user, session_token)
            
    except jwt.DecodeError:
        print("❌ Token JWT mal formé")
        return None
    except Exception as e:
        print(f"❌ Erreur authentification: {e}")
        return None

def create_profile_on_first_login(user_supabase, user, access_token: str):
    """Crée automatiquement un profil lors de la première connexion (cas confirmation email)."""
    try:
        # Récupérer les métadonnées utilisateur depuis Supabase auth
        user_metadata = getattr(user, 'user_metadata', {})
        
        profile_data = {
            "id": user.id,
            "role": "client",  # Toujours client par défaut pour sécurité
            "full_name": user_metadata.get("full_name", "Utilisateur"),
            "email": getattr(user, 'email', None)
        }
        
        # Créer le profil avec le client authentifié (respecte RLS)
        response = user_supabase.table("profiles").insert(profile_data).execute()
        
        if response.data:
            profile = response.data[0]
            profile["_access_token"] = access_token
            print(f"✅ Profil créé automatiquement lors de la première connexion pour {user.email}")
            return profile
        
        return None
    except Exception as e:
        print(f"❌ Erreur création profil automatique: {e}")
        return None

def require_auth(user = Depends(get_current_user)):
    """Middleware pour routes nécessitant une authentification."""
    if not user:
        raise HTTPException(
            status_code=401, 
            detail="Authentification requise",
            headers={"Location": "/login"}
        )
    return user

def require_coach_role(user = Depends(require_auth)):
    """Middleware pour routes réservées aux coaches."""
    if user.get("role") != "coach":
        raise HTTPException(
            status_code=403, 
            detail="Accès réservé aux coaches",
            headers={"Location": "/login"}
        )
    return user

# Routes publiques
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Page d'accueil avec formulaire de recherche."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/search", response_class=HTMLResponse)
async def search_coaches(
    request: Request,
    specialty: Optional[str] = None,
    city: str = "",
    radius_km: int = 25
):
    """Recherche de coachs avec géolocalisation."""
    
    # Géocoder la ville
    coords = geocode_city(city) if city else None
    user_lat, user_lng = coords if coords else (None, None)
    
    # Rechercher les coachs
    if supabase_anon:
        coaches = search_coaches_supabase(supabase_anon, specialty, user_lat, user_lng, radius_km)
    else:
        coaches = search_coaches_mock(specialty, user_lat, user_lng, radius_km)
    
    return templates.TemplateResponse("results.html", {
        "request": request,
        "coaches": coaches,
        "specialty": specialty,
        "city": city,
        "radius_km": radius_km
    })

# Cette route sera déplacée après les routes spécifiques coach/portal, coach/specialties, etc.

# Routes d'authentification
@app.get("/signup", response_class=HTMLResponse)
async def signup_form(request: Request):
    """Formulaire d'inscription."""
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup")
async def signup_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...)
):
    """Traitement de l'inscription."""
    # Validation du mot de passe AVANT d'appeler Supabase
    if not is_valid_password(password):
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": "Mot de passe trop faible (minimum 8 caractères, 1 lettre et 1 chiffre)",
            "full_name": full_name,
            "email": email,
            "role": role
        })
    
    if not supabase_anon:
        # Mode démo sans Supabase
        return RedirectResponse(url="/login", status_code=303)
    
    # Restreindre les rôles autorisés à l'inscription
    if role not in ["client", "coach"]:
        role = "client"
    
    result = sign_up_user(supabase_anon, email, password, full_name, role)
    if result:
        if result.get("requires_confirmation"):
            # Confirmation email requise
            return RedirectResponse(url="/login?message=confirmation_email", status_code=303)
        else:
            # Inscription réussie avec session
            return RedirectResponse(url="/login?message=inscription_reussie", status_code=303)
    else:
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": "Erreur lors de l'inscription. Vérifiez vos informations.",
            "full_name": full_name,
            "email": email,
            "role": role
        })

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, message: Optional[str] = None):
    """Formulaire de connexion."""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "message": message
    })

@app.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    """Traitement de la connexion."""
    if not supabase_anon:
        # Mode démo sans Supabase
        response = RedirectResponse(url="/coach/portal", status_code=303)
        response.set_cookie(
            key="session_token",
            value="demo_token",
            httponly=True,
            secure=False,  # True en production
            samesite="lax"
        )
        return response
    
    result = sign_in_user(supabase_anon, email, password)
    if result and result.get("session"):
        response = RedirectResponse(url="/coach/portal", status_code=303)
        # Cookie HttpOnly sécurisé
        response.set_cookie(
            key="session_token",
            value=result["session"].access_token,
            httponly=True,
            secure=False,  # True en production avec HTTPS
            samesite="lax",
            max_age=3600 * 24 * 7  # 7 jours
        )
        return response
    else:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Email ou mot de passe incorrect."
        })

@app.get("/logout")
async def logout():
    """Déconnexion."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_token")
    return response

# Routes protégées - Espace Coach
@app.get("/coach/portal", response_class=HTMLResponse)
async def coach_portal(request: Request, user = Depends(require_coach_role)):
    """Espace coach - gestion du profil."""
    
    # Récupérer les transformations du coach avec client authentifié
    user_supabase = get_supabase_client_for_user(user.get("_access_token"))
    if user_supabase:
        transformations = get_transformations_by_coach_supabase(user_supabase, user["id"])
    else:
        # Mode démo
        transformations = get_transformations_by_coach_mock(1)
    
    return templates.TemplateResponse("coach_portal.html", {
        "request": request,
        "coach": user,
        "transformations": transformations
    })

@app.post("/coach/portal")
async def coach_portal_update(
    request: Request,
    user = Depends(require_coach_role),
    full_name: str = Form(...),
    bio: str = Form(""),
    city: str = Form(""),
    instagram_url: str = Form(""),
    price_from: Optional[int] = Form(None),
    radius_km: int = Form(25)
):
    """Mise à jour du profil coach."""
    
    profile_data = {
        "full_name": full_name,
        "bio": bio,
        "city": city,
        "instagram_url": instagram_url,
        "price_from": price_from,
        "radius_km": radius_km
    }
    
    user_supabase = get_supabase_client_for_user(user.get("_access_token"))
    if user_supabase:
        success = update_coach_profile(user_supabase, user["id"], profile_data)
        if not success:
            return templates.TemplateResponse("coach_portal.html", {
                "request": request,
                "coach": user,
                "error": "Erreur lors de la mise à jour du profil."
            })
    
    return RedirectResponse(url="/coach/portal", status_code=303)

@app.post("/coach/specialties")
async def coach_specialties_update(
    request: Request,
    user = Depends(require_coach_role),
    specialties: List[str] = Form([])
):
    """Mise à jour des spécialités du coach."""
    
    user_supabase = get_supabase_client_for_user(user.get("_access_token"))
    if user_supabase:
        success = update_coach_specialties(user_supabase, user["id"], specialties)
        if not success:
            return RedirectResponse(url="/coach/portal?error=specialties", status_code=303)
    
    return RedirectResponse(url="/coach/portal", status_code=303)

@app.post("/coach/transformations")
async def coach_transformations_add(
    request: Request,
    user = Depends(require_coach_role),
    title: str = Form(...),
    description: str = Form(""),
    duration_weeks: Optional[int] = Form(None),
    consent: bool = Form(False),
    before_image: Optional[UploadFile] = File(None),
    after_image: Optional[UploadFile] = File(None)
):
    """Ajout d'une transformation."""
    
    if not consent:
        return RedirectResponse(url="/coach/portal?error=consent", status_code=303)
    
    transformation_data = {
        "title": title,
        "description": description,
        "duration_weeks": duration_weeks,
        "consent": consent
    }
    
    user_supabase = get_supabase_client_for_user(user.get("_access_token"))
    if user_supabase:
        # Ajouter la transformation
        transformation = add_transformation(user_supabase, user["id"], transformation_data)
        
        if transformation and (before_image or after_image):
            # Upload des images si fournies
            before_content = before_image.file.read() if before_image else None
            after_content = after_image.file.read() if after_image else None
            
            before_url, after_url = upload_transformation_images(
                user_supabase, transformation["id"], before_content, after_content
            )
            
            # Mettre à jour la transformation avec les URLs des images
            if before_url or after_url:
                update_data = {}
                if before_url:
                    update_data["before_url"] = before_url
                if after_url:
                    update_data["after_url"] = after_url
                
                user_supabase.table("transformations").update(update_data).eq("id", transformation["id"]).execute()
    
    return RedirectResponse(url="/coach/portal", status_code=303)

# Route pour profil de coach - définie APRÈS /coach/portal pour éviter les conflits
@app.get("/coach/{coach_id}", response_class=HTMLResponse)
async def coach_profile(request: Request, coach_id: str):
    """Affichage du profil d'un coach."""
    
    # Récupérer le coach
    if supabase_anon:
        coach = get_coach_by_id_supabase(supabase_anon, coach_id)
        transformations = get_transformations_by_coach_supabase(supabase_anon, coach_id)
    else:
        # Convertir en int pour les données mock si nécessaire
        try:
            coach_id_int = int(coach_id)
            coach = get_coach_by_id_mock(coach_id_int)
            transformations = get_transformations_by_coach_mock(coach_id_int)
        except ValueError:
            coach = None
            transformations = []
    
    if not coach:
        raise HTTPException(status_code=404, detail="Coach non trouvé")
    
    return templates.TemplateResponse("coach.html", {
        "request": request,
        "coach": coach,
        "transformations": transformations
    })

# Route pour les images uploadées (si pas d'utilisation directe de Supabase Storage)
@app.get("/images/{image_path:path}")
async def serve_image(image_path: str):
    """Servir les images uploadées."""
    # Cette route peut être utilisée pour servir des images locales
    # En production, préférer utiliser directement Supabase Storage
    pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
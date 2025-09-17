from fastapi import FastAPI, Request, Form, HTTPException, Depends, File, UploadFile, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional, List
import uvicorn
import jwt
import os
import uuid
import json
from datetime import datetime, timedelta

from utils import (
    geocode_city, 
    search_coaches_mock, 
    get_coach_by_id_mock, 
    get_transformations_by_coach_mock,
    get_supabase_anon_client,
    get_supabase_client_for_user,
    # Nouvelles fonctions Supabase
    sign_in_user,
    get_user_profile,
    search_coaches_supabase,
    get_coach_by_id_supabase,
    get_transformations_by_coach_supabase,
    update_coach_profile,
    update_coach_specialties,
    add_transformation,
    upload_transformation_images,
    resend_confirmation_email,
    create_user_profile_on_confirmation,
    # Fonctions OTP
    generate_otp_code,
    store_otp_code,
    store_otp_code_for_user,
    verify_otp_code,
    cleanup_expired_otp_codes,
    create_user_account_with_otp,
    get_pending_otp_data,
    store_pending_registration,
    # Système coach ↔ salle ↔ client
    geocode_address,
    get_coach_gyms,
    add_coach_gym,
    remove_coach_gym,
    search_gyms_by_location,
    get_coaches_by_gym
)

from resend_service import send_otp_email_resend

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

# Cache en mémoire pour les codes OTP en mode démo (email -> code)
demo_otp_cache = {}
demo_user_cache = {}

# Base de données des salles de sport populaires
GYMS_DATABASE = [
    {"id": "bf_coigniere", "name": "Basic-Fit Coignières", "chain": "Basic-Fit", "lat": 48.7392, "lng": 1.9127, "address": "Centre Commercial Auchan, 78310 Coignières"},
    {"id": "bf_plaisir", "name": "Basic-Fit Plaisir", "chain": "Basic-Fit", "lat": 48.8247, "lng": 1.9504, "address": "Avenue du Général de Gaulle, 78370 Plaisir"},
    {"id": "bf_versailles", "name": "Basic-Fit Versailles", "chain": "Basic-Fit", "lat": 48.8014, "lng": 2.1301, "address": "Boulevard de la Reine, 78000 Versailles"},
    {"id": "fp_saint_quentin", "name": "Fitness Park Saint-Quentin-en-Yvelines", "chain": "Fitness Park", "lat": 48.7838, "lng": 2.0482, "address": "Place Georges Pompidou, 78180 Montigny-le-Bretonneux"},
    {"id": "fp_velizy", "name": "Fitness Park Vélizy", "chain": "Fitness Park", "lat": 48.7804, "lng": 2.1889, "address": "Centre Commercial Vélizy 2, 78140 Vélizy-Villacoublay"},
    {"id": "bf_trappes", "name": "Basic-Fit Trappes", "chain": "Basic-Fit", "lat": 48.7765, "lng": 2.0079, "address": "Centre Commercial Auchan, 78190 Trappes"},
    {"id": "neoness_paris", "name": "Neoness Châtelet", "chain": "Neoness", "lat": 48.8584, "lng": 2.3470, "address": "Forum des Halles, 75001 Paris"},
    {"id": "neoness_defense", "name": "Neoness La Défense", "chain": "Neoness", "lat": 48.8922, "lng": 2.2359, "address": "CNIT, 92800 Puteaux"},
    {"id": "l_orange_bleue_rambouillet", "name": "L'Orange Bleue Rambouillet", "chain": "L'Orange Bleue", "lat": 48.6436, "lng": 1.8287, "address": "Zone d'activité des Closeaux, 78120 Rambouillet"},
    {"id": "keep_cool_mantes", "name": "Keep Cool Mantes-la-Jolie", "chain": "Keep Cool", "lat": 49.0014, "lng": 1.7168, "address": "Avenue du Maréchal Juin, 78200 Mantes-la-Jolie"}
]

# IDs de salles valides pour validation
VALID_GYM_IDS = {gym["id"] for gym in GYMS_DATABASE}

def validate_selected_gyms(selected_gyms_str: str) -> List[str]:
    """Valide et nettoie la liste des salles sélectionnées."""
    if not selected_gyms_str:
        return []
    
    try:
        import json
        selected_gyms = json.loads(selected_gyms_str)
        if not isinstance(selected_gyms, list):
            return []
        
        # Filtrer seulement les IDs valides
        valid_gyms = [gym_id for gym_id in selected_gyms if isinstance(gym_id, str) and gym_id in VALID_GYM_IDS]
        return valid_gyms[:10]  # Limiter à 10 salles max
        
    except json.JSONDecodeError:
        return []
    except Exception:
        return []

# Fonction de validation du mot de passe
def is_valid_password(password: str) -> bool:
    """Valide qu'un mot de passe respecte les critères de sécurité.
    
    Critères: Au moins 8 caractères, une lettre et un chiffre.
    """
    import re
    # Au moins 8 caractères, une lettre et un chiffre (autorisant caractères spéciaux)
    return bool(re.match(r'^(?=.*[A-Za-z])(?=.*\d).{8,}$', password))

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
@app.get("/client/home", response_class=HTMLResponse)
async def client_home(request: Request):
    """Page d'accueil pour les clients avec formulaire de recherche."""
    return templates.TemplateResponse("client_home.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
async def signup_form(request: Request, role: str | None = None):
    """Formulaire d'inscription."""
    return templates.TemplateResponse("signup.html", {
        "request": request, 
        "role": role
    })

@app.get("/api/gyms")
async def get_gyms():
    """API pour récupérer la liste des salles de sport disponibles."""
    return {"gyms": GYMS_DATABASE}

@app.get("/api/user/gyms")
async def get_user_gyms(user = Depends(get_current_user)):
    """Récupère les salles préférées de l'utilisateur connecté."""
    try:
        # Vérifier l'authentification
        if not user:
            return {"success": False, "message": "Utilisateur non connecté", "selected_gyms": []}
        
        user_id = user.get("id")
        email = user.get("email")
        
        if not supabase_anon:
            # Mode démo - chercher dans le cache
            if email in demo_user_cache:
                selected_gyms_str = demo_user_cache[email].get("selected_gyms", "[]")
                try:
                    selected_gyms = json.loads(selected_gyms_str) if selected_gyms_str else []
                    return {"success": True, "selected_gyms": selected_gyms}
                except:
                    return {"success": True, "selected_gyms": []}
            else:
                return {"success": True, "selected_gyms": []}
        else:
            # Mode Supabase - récupérer depuis la base de données
            response = supabase_anon.table("profiles").select("selected_gyms").eq("id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                selected_gyms_str = response.data[0].get("selected_gyms")
                if selected_gyms_str:
                    try:
                        selected_gyms = json.loads(selected_gyms_str)
                        return {"success": True, "selected_gyms": selected_gyms}
                    except:
                        return {"success": True, "selected_gyms": []}
                else:
                    return {"success": True, "selected_gyms": []}
            else:
                return {"success": True, "selected_gyms": []}
                
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des salles utilisateur: {e}")
        return {"success": False, "message": "Erreur serveur", "selected_gyms": []}

@app.post("/api/user/gyms")
async def save_user_gyms(request: Request, user = Depends(get_current_user)):
    """Sauvegarde les salles préférées de l'utilisateur connecté."""
    try:
        # Vérifier l'authentification
        if not user:
            return {"success": False, "message": "Utilisateur non connecté"}
        
        user_id = user.get("id")
        email = user.get("email")
        
        # Récupérer les données JSON de la requête
        body = await request.json()
        selected_gyms = body.get("selected_gyms", [])
        
        # Valider les salles sélectionnées
        validated_gyms = validate_selected_gyms(json.dumps(selected_gyms))
        
        if not supabase_anon:
            # Mode démo - sauvegarder dans le cache
            if email in demo_user_cache:
                demo_user_cache[email]["selected_gyms"] = json.dumps(validated_gyms)
                print(f"✅ Salles sauvegardées en mode démo pour {email}: {validated_gyms}")
                return {"success": True, "message": "Salles sauvegardées avec succès"}
            else:
                return {"success": False, "message": "Utilisateur non trouvé"}
        else:
            # Mode Supabase - sauvegarder dans la base de données
            response = supabase_anon.table("profiles").update({
                "selected_gyms": json.dumps(validated_gyms)
            }).eq("id", user_id).execute()
            
            if response.data:
                print(f"✅ Salles sauvegardées en Supabase pour l'utilisateur {user_id}: {validated_gyms}")
                return {"success": True, "message": "Salles sauvegardées avec succès"}
            else:
                return {"success": False, "message": "Erreur lors de la sauvegarde"}
                
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde des salles: {e}")
        return {"success": False, "message": "Erreur serveur"}

@app.post("/signup")
async def signup_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    gender: str = Form(...),
    role: str = Form(...),
    coach_gender_preference: str = Form("aucune"),
    selected_gyms: str = Form("")
):
    """Inscription utilisateur avec système OTP par email."""
    # Normaliser l'email en lowercase
    email = email.lower().strip()
    
    # Validation du mot de passe
    if not is_valid_password(password):
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": "Mot de passe trop faible (minimum 8 caractères, 1 lettre et 1 chiffre)",
            "full_name": full_name,
            "email": email,
            "gender": gender,
            "role": role,
            "coach_gender_preference": coach_gender_preference
        }, status_code=400)
    
    # Validation du genre
    if gender not in ["homme", "femme"]:
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": "Veuillez sélectionner votre genre",
            "full_name": full_name,
            "email": email,
            "gender": gender,
            "role": role,
            "coach_gender_preference": coach_gender_preference
        }, status_code=400)
    
    # Validation du rôle
    if role not in ["client", "coach"]:
        role = "client"
    
    # Générer le code OTP (6 chiffres par défaut)
    otp_code = generate_otp_code(6)
    
    if not supabase_anon:
        # Mode démo sans Supabase - stocker le code et les infos utilisateur dans le cache
        demo_otp_cache[email] = otp_code
        # Traiter et valider les salles sélectionnées pour les clients
        selected_gyms_list = []
        if role == "client":
            selected_gyms_list = validate_selected_gyms(selected_gyms)
            if selected_gyms and not selected_gyms_list:
                # L'utilisateur a fourni des données invalides
                print(f"⚠️ Salles invalides reçues pour {email}: {selected_gyms}")
                return templates.TemplateResponse("signup.html", {
                    "request": request,
                    "error": "Salles sélectionnées invalides. Veuillez réessayer.",
                    "full_name": full_name,
                    "email": email,
                    "gender": gender,
                    "role": role,
                    "coach_gender_preference": coach_gender_preference
                }, status_code=400)
        
        demo_user_cache[email] = {
            "full_name": full_name,
            "gender": gender,
            "role": role,
            "password": password,  # En production, il faudrait le hasher
            "coach_gender_preference": coach_gender_preference if role == "client" else None,
            "selected_gyms": selected_gyms_list if role == "client" else None
        }
        print(f"🔐 Mode démo - Code OTP généré pour {email}: {otp_code}")
        
        # Tester l'envoi d'email avec Resend même en mode démo
        email_result = send_otp_email_resend(email, otp_code, full_name)
        
        success_message = "Code de vérification envoyé à votre adresse email"
        if email_result.get("success"):
            if email_result.get("mode") == "resend":
                success_message += f" (Email ID: {email_result.get('email_id', 'N/A')})"
        
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "success": success_message
        })
    
    try:
        # Nettoyer les anciens codes expirés
        cleanup_expired_otp_codes(supabase_anon)
        
        # Créer immédiatement le compte Supabase Auth (sans confirmation)
        try:
            auth_response = supabase_anon.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "email_confirm": False,  # Pas de confirmation par email
                    "data": {
                        "full_name": full_name,
                        "role": role
                    }
                }
            })
            
            if not auth_response.user:
                return templates.TemplateResponse("signup.html", {
                    "request": request,
                    "error": "Erreur lors de la création du compte. Veuillez réessayer.",
                    "full_name": full_name,
                    "email": email,
                    "role": role
                }, status_code=500)
            
            user_id = auth_response.user.id
            
        except Exception as e:
            print(f"❌ Erreur création compte Supabase: {e}")
            return templates.TemplateResponse("signup.html", {
                "request": request,
                "error": "Erreur lors de la création du compte. Veuillez réessayer.",
                "full_name": full_name,
                "email": email,
                "role": role
            }, status_code=500)
        
        # Sauvegarder le code OTP en base (avec user_id)
        otp_stored = store_otp_code_for_user(supabase_anon, email, user_id, otp_code)
        
        if not otp_stored:
            return templates.TemplateResponse("signup.html", {
                "request": request,
                "error": "Erreur lors de la génération du code. Veuillez réessayer.",
                "full_name": full_name,
                "email": email,
                "gender": gender,
                "role": role,
                "coach_gender_preference": coach_gender_preference
            }, status_code=500)
        
        # Valider et traiter les salles sélectionnées pour le flux Supabase
        validated_gyms = None
        if role == "client":
            validated_gyms_list = validate_selected_gyms(selected_gyms)
            if selected_gyms and not validated_gyms_list:
                print(f"⚠️ Salles invalides reçues pour {email}: {selected_gyms}")
                return templates.TemplateResponse("signup.html", {
                    "request": request,
                    "error": "Salles sélectionnées invalides. Veuillez réessayer.",
                    "full_name": full_name,
                    "email": email,
                    "gender": gender,
                    "role": role,
                    "coach_gender_preference": coach_gender_preference
                }, status_code=400)
            # Convertir en JSON pour stockage
            validated_gyms = json.dumps(validated_gyms_list) if validated_gyms_list else None
        
        # Sauvegarder les données d'inscription complètes pour récupération après vérification OTP
        pending_stored = store_pending_registration(
            supabase_anon, 
            email, 
            full_name, 
            password, 
            role, 
            gender,
            coach_gender_preference if role == "client" else None,
            validated_gyms
        )
        
        if not pending_stored:
            print("⚠️ Attention: Les données d'inscription supplémentaires n'ont pas pu être sauvegardées")
            # On continue quand même car le compte et l'OTP sont créés
        
        # Envoyer le code par email avec Resend
        email_result = send_otp_email_resend(email, otp_code, full_name)
        
        if email_result.get("success"):
            # Succès - rediriger vers la page de vérification OTP
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "success": "Code de vérification envoyé à votre adresse email"
            })
        else:
            # Échec envoi email - supprimer le code OTP et le compte créé
            try:
                supabase_anon.table("otp_codes").delete().eq("email", email).execute()
                # Note: Supabase Auth ne permet pas de supprimer facilement un utilisateur via l'API
                # En production, implémenter un nettoyage automatique des comptes non vérifiés
            except:
                pass
            
            # Message d'erreur détaillé basé sur le type d'erreur
            error_details = email_result.get("error", "Erreur inconnue")
            if email_result.get("mode") == "resend":
                error_message = f"Erreur d'envoi d'email (Status {email_result.get('status_code', 'N/A')}). Vérifiez votre adresse email et réessayez."
            else:
                error_message = "Erreur de service d'email. Veuillez réessayer dans quelques minutes."
            
            print(f"💥 Détails erreur email: {error_details}")
            
            return templates.TemplateResponse("signup.html", {
                "request": request,
                "error": error_message,
                "full_name": full_name,
                "email": email,
                "role": role
            }, status_code=500)
            
    except Exception as e:
        print(f"❌ Erreur inscription OTP: {e}")
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": "Erreur lors de l'inscription. Veuillez réessayer.",
            "full_name": full_name,
            "email": email,
            "role": role
        }, status_code=500)

@app.post("/verify-otp")
async def verify_otp_submit(
    request: Request,
    email: str = Form(...),
    otp_code: str = Form(...)
):
    """Vérification du code OTP et activation du compte."""
    # Normaliser l'email et le code
    email = email.lower().strip()
    otp_code = otp_code.strip()
    
    # Validation du format du code
    if not otp_code.isdigit() or len(otp_code) < 4 or len(otp_code) > 6:
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "error": "Code invalide. Veuillez saisir un code à 4-6 chiffres."
        }, status_code=400)
    
    if not supabase_anon:
        # Mode démo - vérifier que le code correspond exactement à celui généré
        stored_code = demo_otp_cache.get(email)
        if stored_code and otp_code == stored_code:
            # Code correct - supprimer du cache et connecter
            user_info = demo_user_cache.get(email, {})
            role = user_info.get('role', 'client')
            del demo_otp_cache[email]
            
            # Rediriger selon le rôle
            if role == 'coach':
                redirect_url = "/coach/portal"
            else:
                redirect_url = "/client/home"
                
            response = RedirectResponse(url=redirect_url, status_code=303)
            response.set_cookie(
                key="session_token",
                value="demo_token",
                httponly=True,
                secure=False,  # True en production
                samesite="lax"
            )
            return response
        else:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Code incorrect. Veuillez utiliser le code affiché en mode démo."
            }, status_code=400)
    
    try:
        # Vérifier le code OTP
        otp_valid = verify_otp_code(supabase_anon, email, otp_code)
        
        if not otp_valid:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Code incorrect ou expiré. Veuillez réessayer."
            }, status_code=400)
        
        # Code valide - récupérer les données complètes d'inscription
        pending_data = get_pending_otp_data(supabase_anon, email)
        
        if not pending_data:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Données d'inscription introuvables. Veuillez recommencer l'inscription."
            }, status_code=400)
        
        # Récupérer l'user_id depuis otp_codes
        response = supabase_anon.table("otp_codes").select("user_id").eq("email", email).eq("consumed", True).order("created_at", desc=True).limit(1).execute()
        
        if not response.data:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Utilisateur introuvable. Veuillez recommencer l'inscription."
            }, status_code=400)
        
        user_id = response.data[0]['user_id']
        
        # Extraire les données d'inscription
        full_name = pending_data.get('full_name', '')
        role = pending_data.get('role', 'client')
        gender = pending_data.get('gender')
        coach_gender_preference = pending_data.get('coach_gender_preference')
        selected_gyms = pending_data.get('selected_gyms')
        
        # Créer le profil utilisateur avec toutes les données
        profile_created = create_user_profile_on_confirmation(
            supabase_anon, 
            user_id, 
            email, 
            full_name, 
            role,
            gender,
            coach_gender_preference,
            selected_gyms
        )
        
        # Connecter l'utilisateur
        # Note: En production, il faudrait une vraie session Supabase
        # Pour le mode démo, on va simplement rediriger
        
        # Rediriger selon le rôle
        if role == 'coach':
            redirect_url = "/coach/portal"
        else:
            redirect_url = "/client/home"
        
        response = RedirectResponse(url=redirect_url, status_code=303)
        
        # Cookie de session démo (en production, utiliser un vrai token Supabase)
        response.set_cookie(
            key="session_token",
            value=f"verified_{user_id}",
            httponly=True,
            secure=False,  # True en production avec HTTPS
            samesite="lax",
            max_age=3600 * 24 * 7  # 7 jours
        )
        
        return response
        
    except Exception as e:
            print(f"❌ Erreur récupération utilisateur: {e}")
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Erreur lors de la vérification du compte."
            }, status_code=500)
            
    except Exception as e:
        print(f"❌ Erreur vérification OTP: {e}")
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "error": "Erreur lors de la vérification. Veuillez réessayer."
        }, status_code=500)

@app.post("/resend-otp")
async def resend_otp_submit(
    request: Request,
    email: str = Form(...)
):
    """Renvoie un nouveau code OTP."""
    # Normaliser l'email
    email = email.lower().strip()
    
    if not supabase_anon:
        # Mode démo - générer un nouveau code et le stocker
        new_otp_code = generate_otp_code(6)
        demo_otp_cache[email] = new_otp_code
        print(f"🔐 Mode démo - Nouveau code OTP pour {email}: {new_otp_code}")
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "demo_code": new_otp_code,
            "success": "Nouveau code généré en mode démo"
        })
    
    try:
        # Récupérer les données d'inscription en attente
        pending_data = get_pending_otp_data(supabase_anon, email)
        
        if not pending_data:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Aucune demande d'inscription trouvée pour cet email."
            }, status_code=400)
        
        full_name = pending_data['full_name']
        role = pending_data['role']
        
        # Générer un nouveau code OTP
        new_otp_code = generate_otp_code(6)
        
        # Sauvegarder le nouveau code (l'ancien sera automatiquement supprimé)
        otp_stored = store_otp_code(supabase_anon, email, full_name, role, new_otp_code)
        
        if not otp_stored:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Erreur lors de la génération du nouveau code."
            }, status_code=500)
        
        # Envoyer le nouveau code par email avec Resend
        email_result = send_otp_email_resend(email, new_otp_code, full_name)
        
        if email_result.get("success"):
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "success": "Nouveau code envoyé par email"
            })
        else:
            # Message d'erreur détaillé basé sur le type d'erreur
            error_details = email_result.get("error", "Erreur inconnue")
            if email_result.get("mode") == "resend":
                error_message = f"Erreur d'envoi d'email (Status {email_result.get('status_code', 'N/A')}). Vérifiez votre adresse email et réessayez."
            else:
                error_message = "Erreur de service d'email. Veuillez réessayer dans quelques minutes."
            
            print(f"💥 Détails erreur renvoi email: {error_details}")
            
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": error_message
            }, status_code=500)
            
    except Exception as e:
        print(f"❌ Erreur renvoi OTP: {e}")
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "error": "Erreur lors du renvoi du code."
        }, status_code=500)

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
    # Normaliser l'email en lowercase
    email = email.lower().strip()
    
    if not supabase_anon:
        # Mode démo sans Supabase - vérifier identifiants démo
        if email == "demo@example.com" and password == "demopass123":
            response = RedirectResponse(url="/coach/portal", status_code=303)
            response.set_cookie(
                key="session_token",
                value="demo_token",
                httponly=True,
                secure=False,  # True en production
                samesite="lax"
            )
            return response
        else:
            # Identifiants incorrects même en mode démo
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Email ou mot de passe incorrect.",
                "email": email
            }, status_code=401)
    
    # Mode Supabase - utiliser exclusivement signInWithPassword
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
    elif result and result.get("error"):
        # Vérifier si c'est un problème d'email non confirmé
        error_message = result["error"].lower()
        if "email not confirmed" in error_message or "not confirmed" in error_message:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Email non confirmé",
                "email": email,
                "show_resend": True
            }, status_code=401)
        else:
            # Autre erreur d'authentification
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Email ou mot de passe incorrect.",
                "email": email
            }, status_code=401)
    else:
        # Retourner template avec email conservé - HTTP 401 sans redirection
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Email ou mot de passe incorrect.",
            "email": email
        }, status_code=401)

@app.post("/auth/resend-confirmation")
async def resend_confirmation(
    request: Request,
    email: str = Form(...)
):
    """Renvoie l'email de confirmation."""
    # Normaliser l'email en lowercase
    email = email.lower().strip()
    
    if not supabase_anon:
        # Mode démo - pas de renvoi d'email
        return templates.TemplateResponse("verify_email.html", {
            "request": request,
            "email": email,
            "error": "Mode démo - renvoi d'email non disponible"
        })
    
    success = resend_confirmation_email(supabase_anon, email)
    if success:
        return templates.TemplateResponse("verify_email.html", {
            "request": request,
            "email": email,
            "success": "Email de confirmation renvoyé ! Vérifiez votre boîte mail."
        })
    else:
        return templates.TemplateResponse("verify_email.html", {
            "request": request,
            "email": email,
            "error": "Erreur lors du renvoi de l'email. Veuillez réessayer."
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

# ======================================
# ENDPOINTS API COACH - GESTION DES LIEUX
# ======================================

@app.get("/api/coach/gyms")
async def get_coach_gym_locations(user = Depends(require_coach_role)):
    """Récupère les lieux de coaching d'un coach."""
    try:
        coach_id = str(user["id"])
        gym_relations = get_coach_gyms(coach_id)
        
        return {
            "success": True,
            "gyms": gym_relations
        }
        
    except Exception as e:
        print(f"Erreur récupération lieux coach: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la récupération des lieux",
            "gyms": []
        }

@app.post("/api/coach/gyms")
async def add_coach_gym_location(
    request: Request,
    user = Depends(require_coach_role)
):
    """Ajoute un lieu de coaching pour un coach."""
    try:
        coach_id = str(user["id"])
        
        # Récupérer les données JSON de la requête
        data = await request.json()
        
        # Valider les données requises
        if "query" not in data:
            return {
                "success": False,
                "message": "Adresse ou nom de salle requis"
            }
        
        query = data["query"].strip()
        if not query:
            return {
                "success": False,
                "message": "Adresse ne peut pas être vide"
            }
        
        # Géocoder l'adresse
        geocoded = geocode_address(query)
        if not geocoded:
            return {
                "success": False,
                "message": f"Impossible de localiser '{query}'. Vérifiez l'adresse."
            }
        
        # Ajouter la relation coach-salle
        success = add_coach_gym(coach_id, geocoded)
        
        if success:
            return {
                "success": True,
                "message": f"Lieu '{geocoded['name']}' ajouté avec succès",
                "gym": geocoded
            }
        else:
            return {
                "success": False,
                "message": "Ce lieu est déjà dans votre liste"
            }
            
    except Exception as e:
        print(f"Erreur ajout lieu coach: {e}")
        return {
            "success": False,
            "message": "Erreur lors de l'ajout du lieu"
        }

@app.delete("/api/coach/gyms/{gym_id}")
async def remove_coach_gym_location(
    gym_id: str,
    user = Depends(require_coach_role)
):
    """Supprime un lieu de coaching d'un coach."""
    try:
        coach_id = str(user["id"])
        
        success = remove_coach_gym(coach_id, gym_id)
        
        if success:
            return {
                "success": True,
                "message": "Lieu supprimé avec succès"
            }
        else:
            return {
                "success": False,
                "message": "Lieu non trouvé ou non autorisé"
            }
            
    except Exception as e:
        print(f"Erreur suppression lieu coach: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la suppression"
        }

# ======================================
# ENDPOINTS API CLIENT - RECHERCHE SALLES
# ======================================

@app.get("/api/gyms/search")
async def search_gyms_by_location_api(
    q: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: int = 25
):
    """
    Recherche de salles par localisation ou nom.
    Paramètres: q (nom/adresse) OU lat,lng + radius_km
    """
    try:
        results = []
        
        if q:
            # Recherche par nom/adresse - géocoder d'abord
            geocoded = geocode_address(q)
            if geocoded:
                results = search_gyms_by_location(
                    geocoded["lat"], 
                    geocoded["lng"], 
                    radius_km
                )
            else:
                # Recherche par nom dans GYMS_DATABASE si géocodage échoue
                for gym in GYMS_DATABASE:
                    if q.lower() in gym["name"].lower() or q.lower() in gym["address"].lower():
                        # Compter les coachs dans cette salle
                        coach_count = len(get_coaches_by_gym(gym["address"]))
                        gym_result = gym.copy()
                        gym_result["distance_km"] = None  # Pas de distance si recherche par nom
                        gym_result["coach_count"] = coach_count
                        results.append(gym_result)
        
        elif lat is not None and lng is not None:
            # Recherche par coordonnées
            results = search_gyms_by_location(lat, lng, radius_km)
        
        else:
            return {
                "success": False,
                "message": "Paramètres requis: 'q' (recherche) OU 'lat' + 'lng'",
                "gyms": []
            }
        
        return {
            "success": True,
            "gyms": results,
            "count": len(results)
        }
        
    except Exception as e:
        print(f"Erreur recherche salles: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la recherche",
            "gyms": []
        }

@app.get("/api/gyms/{gym_address:path}/coaches")
async def get_gym_coaches(gym_address: str):
    """
    Récupère tous les coachs disponibles dans une salle spécifique.
    gym_address: adresse complète de la salle
    """
    try:
        # Décoder l'adresse (au cas où elle est URL-encodée)
        from urllib.parse import unquote
        gym_address = unquote(gym_address)
        
        coaches = get_coaches_by_gym(gym_address)
        
        # Ajouter des infos spécifiques à la salle si nécessaire
        enhanced_coaches = []
        for coach in coaches:
            enhanced_coach = coach.copy()
            # Ici on pourrait ajouter des infos spécifiques comme prix dans cette salle
            # Pour l'instant, on garde les infos de base
            enhanced_coaches.append(enhanced_coach)
        
        return {
            "success": True,
            "coaches": enhanced_coaches,
            "count": len(enhanced_coaches),
            "gym_address": gym_address
        }
        
    except Exception as e:
        print(f"Erreur récupération coachs pour salle '{gym_address}': {e}")
        return {
            "success": False,
            "message": "Erreur lors de la récupération des coachs",
            "coaches": []
        }

@app.get("/api/gyms/{gym_id}/coaches")  
async def get_gym_coaches_by_id(gym_id: str):
    """
    Récupère tous les coachs disponibles dans une salle par ID.
    Fallback pour gym_id au lieu d'adresse complète.
    """
    try:
        # Chercher la salle par ID dans GYMS_DATABASE
        gym = next((g for g in GYMS_DATABASE if g["id"] == gym_id), None)
        
        if not gym:
            return {
                "success": False,
                "message": f"Salle avec ID '{gym_id}' non trouvée",
                "coaches": []
            }
        
        # Utiliser l'adresse pour chercher les coachs
        coaches = get_coaches_by_gym(gym["address"])
        
        return {
            "success": True,
            "coaches": coaches,
            "count": len(coaches),
            "gym": gym
        }
        
    except Exception as e:
        print(f"Erreur récupération coachs pour salle ID '{gym_id}': {e}")
        return {
            "success": False,
            "message": "Erreur lors de la récupération des coachs",
            "coaches": []
        }

# Route pour les images uploadées (si pas d'utilisation directe de Supabase Storage)
@app.get("/images/{image_path:path}")
async def serve_image(image_path: str):
    """Servir les images uploadées."""
    # Cette route peut être utilisée pour servir des images locales
    # En production, préférer utiliser directement Supabase Storage
    pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
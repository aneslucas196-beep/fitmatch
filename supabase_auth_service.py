"""
Service pour l'authentification Supabase avec email de confirmation intégré
Remplace le système Resend pour utiliser le service email natif de Supabase
"""
import os
from typing import Optional, Dict
from supabase import create_client, Client

def get_supabase_client() -> Optional[Client]:
    """Initialise le client Supabase pour l'authentification."""
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        print("⚠️ SUPABASE_URL ou SUPABASE_KEY manquant")
        return None
    
    return create_client(supabase_url, supabase_key)

def signup_with_supabase_email_confirmation(
    email: str, 
    password: str, 
    full_name: str, 
    role: str,
    redirect_url: Optional[str] = None
) -> Dict:
    """
    Inscription avec confirmation email native Supabase
    Retourne un dictionnaire avec success (bool) et des détails
    """
    try:
        client = get_supabase_client()
        if not client:
            return {
                "success": False,
                "error": "Configuration Supabase manquante",
                "mode": "config_error"
            }
        
        # URL de redirection après confirmation email (prod: SITE_URL)
        if not redirect_url:
            site_url = os.environ.get('SITE_URL') or os.environ.get('REPLIT_DEV_DOMAIN', 'http://localhost:5000')
            if site_url and not site_url.startswith('http'):
                site_url = f"https://{site_url}"
            redirect_url = f"{site_url.rstrip('/')}/auth/email-confirmed"
        
        print(f"🔧 Inscription Supabase avec confirmation email:")
        print(f"  - Email: {email}")
        print(f"  - URL de redirection: {redirect_url}")
        
        # Inscription avec confirmation email automatique
        auth_response = client.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "email_confirm": True,  # Active l'envoi automatique de l'email de confirmation
                "redirect_to": redirect_url,
                "data": {
                    "full_name": full_name,
                    "role": role
                }
            }
        })
        
        if auth_response.user:
            print(f"✅ Compte créé avec succès pour {email}")
            print(f"📧 Email de confirmation envoyé automatiquement par Supabase")
            
            return {
                "success": True,
                "mode": "supabase_native",
                "user_id": auth_response.user.id,
                "email": email,
                "email_confirmed": auth_response.user.email_confirmed_at is not None,
                "message": "Email de confirmation envoyé à votre adresse"
            }
        else:
            return {
                "success": False,
                "error": "Erreur lors de la création du compte",
                "mode": "signup_error"
            }
            
    except Exception as e:
        print(f"❌ Erreur inscription Supabase: {e}")
        return {
            "success": False,
            "error": str(e),
            "mode": "exception"
        }

def resend_email_confirmation(email: str) -> Dict:
    """
    Renvoie l'email de confirmation Supabase
    """
    try:
        client = get_supabase_client()
        if not client:
            return {
                "success": False,
                "error": "Configuration Supabase manquante"
            }
        
        # Utiliser la méthode Supabase pour renvoyer l'email de confirmation
        result = client.auth.resend({
            "type": "signup",
            "email": email
        })
        
        print(f"📧 Email de confirmation renvoyé pour {email}")
        
        return {
            "success": True,
            "message": "Email de confirmation renvoyé",
            "mode": "supabase_resend"
        }
        
    except Exception as e:
        print(f"❌ Erreur renvoi email confirmation: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def sign_in_with_email_password(email: str, password: str) -> Dict:
    """
    Connexion avec email et mot de passe après confirmation
    """
    try:
        client = get_supabase_client()
        if not client:
            return {
                "success": False,
                "error": "Configuration Supabase manquante"
            }
        
        # Connexion classique email/password
        auth_response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if auth_response.user and auth_response.session:
            # Vérifier que l'email est confirmé
            if not auth_response.user.email_confirmed_at:
                return {
                    "success": False,
                    "error": "Email non confirmé. Vérifiez votre boîte mail.",
                    "mode": "email_not_confirmed"
                }
            
            print(f"✅ Connexion réussie pour {email}")
            return {
                "success": True,
                "user": auth_response.user,
                "session": auth_response.session,
                "mode": "email_password"
            }
        else:
            return {
                "success": False,
                "error": "Email ou mot de passe incorrect",
                "mode": "invalid_credentials"
            }
            
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")
        return {
            "success": False,
            "error": str(e),
            "mode": "exception"
        }

def get_user_role(user_id: str) -> Dict:
    """
    Récupère le profil utilisateur depuis Supabase pour déterminer le rôle
    """
    try:
        client = get_supabase_client()
        if not client:
            return {
                "success": False,
                "error": "Configuration Supabase manquante"
            }
        
        # Récupérer le profil depuis la table users
        response = client.table('users').select('role').eq('id', user_id).single().execute()
        
        if response.data:
            return {
                "success": True,
                "role": response.data.get('role'),
                "user_id": user_id
            }
        else:
            return {
                "success": False,
                "error": "Profil utilisateur non trouvé"
            }
            
    except Exception as e:
        print(f"❌ Erreur récupération profil: {e}")
        return {
            "success": False,
            "error": str(e)
        }
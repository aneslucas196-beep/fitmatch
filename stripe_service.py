"""
Service Stripe pour les abonnements mensuels des coachs FitMatch
"""

import stripe
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any

# Prix de l'abonnement mensuel coach (en centimes)
COACH_MONTHLY_PRICE = 100  # 1€/mois


async def get_stripe_credentials() -> Dict[str, str]:
    """
    Récupère les credentials Stripe depuis la connexion Replit.
    """
    import aiohttp
    
    hostname = os.environ.get("REPLIT_CONNECTORS_HOSTNAME")
    
    # Token d'authentification Replit
    repl_identity = os.environ.get("REPL_IDENTITY")
    web_repl_renewal = os.environ.get("WEB_REPL_RENEWAL")
    
    if repl_identity:
        x_replit_token = f"repl {repl_identity}"
    elif web_repl_renewal:
        x_replit_token = f"depl {web_repl_renewal}"
    else:
        raise Exception("Pas de token Replit disponible")
    
    # Essayer d'abord production, puis development
    for target_environment in ["production", "development"]:
        url = f"https://{hostname}/api/v2/connection?include_secrets=true&connector_names=stripe&environment={target_environment}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={
                "Accept": "application/json",
                "X_REPLIT_TOKEN": x_replit_token
            }) as response:
                data = await response.json()
        
        items = data.get("items", [])
        if items:
            connection = items[0]
            settings = connection.get("settings", {})
            
            publishable_key = settings.get("publishable")
            secret_key = settings.get("secret")
            
            if publishable_key and secret_key:
                print(f"✅ Utilisation des clés Stripe {target_environment}")
                return {
                    "publishable_key": publishable_key,
                    "secret_key": secret_key
                }
    
    raise Exception("Aucune connexion Stripe trouvée (ni production, ni development)")


def get_stripe_credentials_sync() -> Dict[str, str]:
    """
    Version synchrone pour récupérer les credentials Stripe.
    Essaie d'abord production, puis development si production n'est pas configuré.
    """
    import requests
    
    hostname = os.environ.get("REPLIT_CONNECTORS_HOSTNAME")
    
    repl_identity = os.environ.get("REPL_IDENTITY")
    web_repl_renewal = os.environ.get("WEB_REPL_RENEWAL")
    
    if repl_identity:
        x_replit_token = f"repl {repl_identity}"
    elif web_repl_renewal:
        x_replit_token = f"depl {web_repl_renewal}"
    else:
        raise Exception("Pas de token Replit disponible")
    
    # Essayer d'abord production, puis development
    for target_environment in ["production", "development"]:
        url = f"https://{hostname}/api/v2/connection?include_secrets=true&connector_names=stripe&environment={target_environment}"
        
        response = requests.get(url, headers={
            "Accept": "application/json",
            "X_REPLIT_TOKEN": x_replit_token
        })
        data = response.json()
        
        items = data.get("items", [])
        if items:
            connection = items[0]
            settings = connection.get("settings", {})
            
            publishable_key = settings.get("publishable")
            secret_key = settings.get("secret")
            
            if publishable_key and secret_key:
                print(f"✅ Utilisation des clés Stripe {target_environment}")
                return {
                    "publishable_key": publishable_key,
                    "secret_key": secret_key
                }
    
    raise Exception("Aucune connexion Stripe trouvée (ni production, ni development)")


def init_stripe():
    """Initialise Stripe avec la clé secrète."""
    credentials = get_stripe_credentials_sync()
    stripe.api_key = credentials["secret_key"]
    return credentials


def get_publishable_key() -> str:
    """Retourne la clé publique Stripe."""
    credentials = get_stripe_credentials_sync()
    return credentials["publishable_key"]


def create_or_get_customer(email: str, name: str, coach_id: str) -> stripe.Customer:
    """
    Crée ou récupère un customer Stripe pour un coach.
    """
    init_stripe()
    
    # Chercher si le customer existe déjà
    customers = stripe.Customer.list(email=email, limit=1)
    
    if customers.data:
        return customers.data[0]
    
    # Créer un nouveau customer
    customer = stripe.Customer.create(
        email=email,
        name=name,
        metadata={
            "coach_id": coach_id,
            "platform": "fitmatch"
        }
    )
    return customer


def create_checkout_session(
    customer_id: str,
    success_url: str,
    cancel_url: str,
    coach_email: str
) -> stripe.checkout.Session:
    """
    Crée une session Checkout Stripe pour l'abonnement mensuel.
    """
    init_stripe()
    
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {
                    "name": "FitMatch Pro - Abonnement Coach",
                    "description": "Accès complet à la plateforme FitMatch pour les coachs",
                    "images": ["https://fitmatch.fr/logo.png"]
                },
                "unit_amount": COACH_MONTHLY_PRICE,
                "recurring": {
                    "interval": "month"
                }
            },
            "quantity": 1
        }],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "coach_email": coach_email,
            "subscription_type": "coach_monthly"
        },
        subscription_data={
            "metadata": {
                "coach_email": coach_email,
                "subscription_type": "coach_monthly"
            }
        }
    )
    return session


def create_portal_session(customer_id: str, return_url: str) -> stripe.billing_portal.Session:
    """
    Crée une session du portail de facturation Stripe.
    """
    init_stripe()
    
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url
    )
    return session


def get_subscription_status(subscription_id: str) -> Dict[str, Any]:
    """
    Récupère le statut d'un abonnement.
    """
    init_stripe()
    
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        return {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end).isoformat(),
            "cancel_at_period_end": subscription.cancel_at_period_end
        }
    except Exception as e:
        return {"error": str(e)}


def cancel_subscription(subscription_id: str, immediately: bool = False) -> Dict[str, Any]:
    """
    Annule un abonnement (à la fin de la période ou immédiatement).
    """
    init_stripe()
    
    try:
        if immediately:
            subscription = stripe.Subscription.delete(subscription_id)
        else:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
        return {
            "id": subscription.id,
            "status": subscription.status,
            "cancel_at_period_end": subscription.cancel_at_period_end
        }
    except Exception as e:
        return {"error": str(e)}


def verify_webhook_signature(payload: bytes, sig_header: str, webhook_secret: str) -> stripe.Event:
    """
    Vérifie la signature d'un webhook Stripe.
    """
    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)


# ============================================
# GESTION DES ABONNEMENTS DANS demo_users.json
# ============================================

def load_demo_users() -> dict:
    """Charge les utilisateurs depuis demo_users.json."""
    try:
        if os.path.exists("demo_users.json"):
            with open("demo_users.json", "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Erreur chargement demo_users: {e}")
    return {"users": []}


def save_demo_users(data: dict):
    """Sauvegarde les utilisateurs dans demo_users.json."""
    try:
        with open("demo_users.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erreur sauvegarde demo_users: {e}")


def update_coach_subscription(
    coach_email: str,
    stripe_customer_id: str = None,
    stripe_subscription_id: str = None,
    subscription_status: str = None,
    current_period_end: str = None
):
    """
    Met à jour les informations d'abonnement d'un coach.
    """
    data = load_demo_users()
    
    for user in data.get("users", []):
        if user.get("email") == coach_email and user.get("role") == "coach":
            if stripe_customer_id:
                user["stripe_customer_id"] = stripe_customer_id
            if stripe_subscription_id:
                user["stripe_subscription_id"] = stripe_subscription_id
            if subscription_status:
                user["subscription_status"] = subscription_status
            if current_period_end:
                user["subscription_period_end"] = current_period_end
            
            save_demo_users(data)
            return True
    
    return False


def get_coach_subscription_info(coach_email: str) -> Optional[Dict[str, Any]]:
    """
    Récupère les informations d'abonnement d'un coach.
    """
    data = load_demo_users()
    
    for user in data.get("users", []):
        if user.get("email") == coach_email and user.get("role") == "coach":
            return {
                "stripe_customer_id": user.get("stripe_customer_id"),
                "stripe_subscription_id": user.get("stripe_subscription_id"),
                "subscription_status": user.get("subscription_status", "inactive"),
                "subscription_period_end": user.get("subscription_period_end")
            }
    
    return None


def is_coach_subscribed(coach_email: str) -> bool:
    """
    Vérifie si un coach a un abonnement actif.
    """
    info = get_coach_subscription_info(coach_email)
    if not info:
        return False
    
    status = info.get("subscription_status")
    return status in ["active", "trialing"]

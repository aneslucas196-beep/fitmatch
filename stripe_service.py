"""
Service Stripe pour les abonnements mensuels des coachs FitMatch
"""

import stripe
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any

# Prix de l'abonnement mensuel coach (en centimes)
COACH_MONTHLY_PRICE = 2900  # 29€/mois
COACH_ANNUAL_PRICE = 56000  # 560€/an (réduit de 20% par rapport à 720€)


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
    
    # Utiliser les clés depuis les variables d'environnement
    publishable_key = os.environ.get("STRIPE_PUBLIC_KEY")
    secret_key = os.environ.get("STRIPE_SECRET_KEY")
    
    if publishable_key and secret_key:
        print(f"✅ Utilisation des clés Stripe depuis les secrets")
        return {
            "publishable_key": publishable_key,
            "secret_key": secret_key
        }
    
    raise Exception("Clés Stripe non configurées. Ajoutez STRIPE_PUBLIC_KEY et STRIPE_SECRET_KEY dans les secrets.")


def get_stripe_credentials_sync() -> Dict[str, str]:
    """
    Récupère les credentials Stripe depuis les variables d'environnement.
    """
    publishable_key = os.environ.get("STRIPE_PUBLIC_KEY")
    secret_key = os.environ.get("STRIPE_SECRET_KEY")
    
    if publishable_key and secret_key:
        print(f"✅ Utilisation des clés Stripe depuis les secrets")
        return {
            "publishable_key": publishable_key,
            "secret_key": secret_key
        }
    
    raise Exception("Clés Stripe non configurées. Ajoutez STRIPE_PUBLIC_KEY et STRIPE_SECRET_KEY dans les secrets.")


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
    coach_email: str,
    billing_period: str = "monthly"
) -> stripe.checkout.Session:
    """
    Crée une session Checkout Stripe pour l'abonnement.
    billing_period: "monthly" (29€/mois) ou "annual" (560€/an avec -20% réduction)
    """
    init_stripe()
    
    if billing_period == "annual":
        unit_amount = COACH_ANNUAL_PRICE
        interval = "year"
        subscription_type = "coach_annual"
    else:
        unit_amount = COACH_MONTHLY_PRICE
        interval = "month"
        subscription_type = "coach_monthly"
    
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
                "unit_amount": unit_amount,
                "recurring": {
                    "interval": interval
                }
            },
            "quantity": 1
        }],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "coach_email": coach_email,
            "subscription_type": subscription_type
        },
        subscription_data={
            "metadata": {
                "coach_email": coach_email,
                "subscription_type": subscription_type
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
    
    # Structure: {"email": {user_data}, ...} pas {"users": [...]}
    if coach_email in data:
        user = data[coach_email]
        if stripe_customer_id:
            user["stripe_customer_id"] = stripe_customer_id
        if stripe_subscription_id:
            user["stripe_subscription_id"] = stripe_subscription_id
        if subscription_status:
            user["subscription_status"] = subscription_status
        if current_period_end:
            user["subscription_period_end"] = current_period_end
        
        save_demo_users(data)
        print(f"✅ Abonnement mis à jour pour {coach_email}: status={subscription_status}")
        return True
    
    print(f"⚠️ Coach {coach_email} non trouvé dans demo_users")
    return False


def get_coach_subscription_info(coach_email: str) -> Optional[Dict[str, Any]]:
    """
    Récupère les informations d'abonnement d'un coach.
    """
    data = load_demo_users()
    
    # Structure: {"email": {user_data}, ...}
    if coach_email in data:
        user = data[coach_email]
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

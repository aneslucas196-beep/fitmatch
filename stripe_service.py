"""
Service Stripe pour les abonnements mensuels des coachs FitMatch
"""

import stripe
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any

# Prix abonnement coach (en centimes)
COACH_MONTHLY_PRICE = 3000   # 30€/mois
COACH_ANNUAL_PRICE = 30000   # 300€/an (équivalent 10 mois)


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
    
    publishable_key = os.environ.get("STRIPE_PUBLISHABLE_KEY") or os.environ.get("STRIPE_PUBLIC_KEY")
    secret_key = os.environ.get("STRIPE_SECRET_KEY")
    if publishable_key and secret_key:
        return {"publishable_key": publishable_key, "secret_key": secret_key}
    raise Exception("Clés Stripe non configurées. Ajoutez STRIPE_PUBLISHABLE_KEY (ou STRIPE_PUBLIC_KEY) et STRIPE_SECRET_KEY.")


def get_stripe_credentials_sync() -> Dict[str, str]:
    """Récupère les credentials Stripe (Render / env)."""
    publishable_key = os.environ.get("STRIPE_PUBLISHABLE_KEY") or os.environ.get("STRIPE_PUBLIC_KEY")
    secret_key = os.environ.get("STRIPE_SECRET_KEY")
    if publishable_key and secret_key:
        return {"publishable_key": publishable_key, "secret_key": secret_key}
    raise Exception("Clés Stripe non configurées. STRIPE_PUBLISHABLE_KEY et STRIPE_SECRET_KEY requis.")


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
    billing_period: "monthly" (30€/mois) ou "annual" (300€/an)
    Si STRIPE_PRICE_ID (ou STRIPE_MONTHLY_PRICE_ID) est défini, utilise ce Price ID.
    Sinon utilise price_data (dynamic).
    """
    init_stripe()
    
    if not customer_id:
        print("❌ Erreur: customer_id manquant pour create_checkout_session")
        raise Exception("customer_id manquant")

    if billing_period == "annual":
        unit_amount = COACH_ANNUAL_PRICE
        interval = "year"
        subscription_type = "coach_annual"
        price_id = os.environ.get("STRIPE_ANNUAL_PRICE_ID") or ""
    else:
        unit_amount = COACH_MONTHLY_PRICE
        interval = "month"
        subscription_type = "coach_monthly"
        price_id = (os.environ.get("STRIPE_PRICE_ID") or os.environ.get("STRIPE_MONTHLY_PRICE_ID") or "").strip()

    if price_id and price_id.startswith("price_"):
        # Utiliser un Price ID existant (Dashboard Stripe)
        line_items = [{"price": price_id, "quantity": 1}]
        print(f"💳 Création session avec Price ID: {price_id[:20]}...")
    else:
        # Mode dynamique (price_data)
        line_items = [{
            "price_data": {
                "currency": "eur",
                "product_data": {
                    "name": "FitMatch Pro - Abonnement Coach",
                    "description": "Accès complet à la plateforme FitMatch pour les coachs",
                },
                "unit_amount": unit_amount,
                "recurring": {"interval": interval}
            },
            "quantity": 1
        }]
    
    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            mode="subscription",
            line_items=line_items,
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
    except Exception as e:
        print(f"❌ Erreur stripe.checkout.Session.create: {e}")
        raise e


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
# GESTION DES ABONNEMENTS (base de données)
# ============================================

def update_coach_subscription(
    coach_email: str,
    stripe_customer_id: str = None,
    stripe_subscription_id: str = None,
    subscription_status: str = None,
    current_period_end: str = None
):
    """
    Met à jour les informations d'abonnement d'un coach (PostgreSQL).
    """
    try:
        from utils import get_demo_user, save_demo_user
    except ImportError:
        print("⚠️ utils non disponible pour update_coach_subscription")
        return False
    user = get_demo_user(coach_email)
    if not user:
        print(f"⚠️ Coach {coach_email} non trouvé en base")
        return False
    if stripe_customer_id is not None:
        user["stripe_customer_id"] = stripe_customer_id
    if stripe_subscription_id is not None:
        user["stripe_subscription_id"] = stripe_subscription_id
    if subscription_status is not None:
        user["subscription_status"] = subscription_status
    if current_period_end is not None:
        user["subscription_period_end"] = current_period_end
    ok = save_demo_user(coach_email, user)
    if ok:
        print(f"✅ Abonnement mis à jour pour {coach_email}: status={subscription_status}")
    return ok


def get_coach_subscription_info(coach_email: str) -> Optional[Dict[str, Any]]:
    """
    Récupère les informations d'abonnement d'un coach (PostgreSQL).
    """
    try:
        from utils import get_demo_user
    except ImportError:
        return None
    user = get_demo_user(coach_email)
    if not user:
        return None
    return {
        "stripe_customer_id": user.get("stripe_customer_id"),
        "stripe_subscription_id": user.get("stripe_subscription_id"),
        "subscription_status": user.get("subscription_status", "inactive"),
        "subscription_period_end": user.get("subscription_period_end")
    }


def is_coach_subscribed(coach_email: str) -> bool:
    """
    Vérifie si un coach a un abonnement actif.
    """
    info = get_coach_subscription_info(coach_email)
    if not info:
        return False
    
    status = info.get("subscription_status")
    return status in ["active", "trialing"]

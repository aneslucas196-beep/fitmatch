"""
Service Stripe Connect pour FitMatch
Gère les comptes Connect des coachs pour recevoir les paiements des clients
"""

import stripe
import os
from typing import Optional, Dict, Any
from datetime import datetime

def init_stripe():
    """Initialise Stripe avec la clé secrète."""
    secret_key = os.environ.get("STRIPE_SECRET_KEY")
    if not secret_key:
        raise Exception("STRIPE_SECRET_KEY non configuré")
    stripe.api_key = secret_key
    return secret_key


def create_connect_account(coach_email: str, coach_name: str) -> Dict[str, Any]:
    """
    Crée un compte Stripe Connect Standard pour un coach.
    Retourne l'account_id créé.
    """
    
    init_stripe()
    
    try:
        account = stripe.Account.create(
            type="standard",
            email=coach_email,
            metadata={
                "platform": "fitmatch",
                "coach_email": coach_email,
                "coach_name": coach_name
            }
        )
        
        return {
            "success": True,
            "account_id": account.id,
            "details_submitted": account.details_submitted,
            "charges_enabled": account.charges_enabled,
            "payouts_enabled": account.payouts_enabled
        }
    except stripe.error.StripeError as e:
        return {
            "success": False,
            "error": str(e)
        }


def create_account_link(account_id: str, return_url: str, refresh_url: str) -> Dict[str, Any]:
    """
    Crée un lien d'onboarding Stripe Connect pour que le coach configure son compte.
    Ce lien redirige vers Stripe pour collecter les infos bancaires.
    """
    init_stripe()
    
    try:
        account_link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding"
        )
        
        return {
            "success": True,
            "url": account_link.url,
            "expires_at": account_link.expires_at
        }
    except stripe.error.StripeError as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_account_status(account_id: str) -> Dict[str, Any]:
    """
    Récupère le statut actuel d'un compte Connect.
    Vérifie si le compte peut recevoir des paiements.
    """
    
    if account_id and account_id.startswith("acct_demo_"):
        return {
            "success": True,
            "account_id": account_id,
            "status": "active",
            "details_submitted": True,
            "charges_enabled": True,
            "payouts_enabled": True,
            "currently_due": [],
            "eventually_due": [],
            "past_due": [],
            "email": "demo@fitmatch.local",
            "country": "FR",
            "default_currency": "eur"
        }
    
    # Mode réel: utiliser Stripe
    init_stripe()
    
    try:
        account = stripe.Account.retrieve(account_id)
        
        requirements = account.requirements or {}
        currently_due = requirements.get("currently_due", [])
        eventually_due = requirements.get("eventually_due", [])
        past_due = requirements.get("past_due", [])
        
        status = "inactive"
        if account.charges_enabled and account.payouts_enabled:
            status = "active"
        elif account.details_submitted:
            status = "pending"
        elif currently_due or past_due:
            status = "incomplete"
        
        return {
            "success": True,
            "account_id": account.id,
            "status": status,
            "details_submitted": account.details_submitted,
            "charges_enabled": account.charges_enabled,
            "payouts_enabled": account.payouts_enabled,
            "currently_due": currently_due,
            "eventually_due": eventually_due,
            "past_due": past_due,
            "email": account.email,
            "country": account.country,
            "default_currency": account.default_currency
        }
    except stripe.error.StripeError as e:
        return {
            "success": False,
            "error": str(e)
        }


def create_login_link(account_id: str) -> Dict[str, Any]:
    """
    Crée un lien pour que le coach accède à son dashboard Stripe Express.
    Uniquement pour les comptes Express, pas Standard.
    Pour Standard, le coach utilise son propre dashboard Stripe.
    """
    init_stripe()
    
    try:
        login_link = stripe.Account.create_login_link(account_id)
        return {
            "success": True,
            "url": login_link.url
        }
    except stripe.error.StripeError as e:
        return {
            "success": False,
            "error": str(e)
        }


def create_session_payment_checkout(
    coach_account_id: str,
    coach_email: str,
    client_email: str,
    client_name: str,
    amount_cents: int,
    service_name: str,
    booking_id: str,
    success_url: str,
    cancel_url: str
) -> Dict[str, Any]:
    """
    Crée une session Stripe Checkout pour payer une séance.
    L'argent va directement au coach (via transfer_data).
    FitMatch ne prend pas de commission sur les séances.
    """
    init_stripe()
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": service_name,
                        "description": f"Séance avec {coach_email}"
                    },
                    "unit_amount": amount_cents
                },
                "quantity": 1
            }],
            payment_intent_data={
                "transfer_data": {
                    "destination": coach_account_id
                },
                "metadata": {
                    "booking_id": booking_id,
                    "coach_email": coach_email,
                    "client_email": client_email,
                    "client_name": client_name,
                    "booking_type": "session_payment"
                }
            },
            customer_email=client_email,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "booking_id": booking_id,
                "coach_email": coach_email,
                "client_email": client_email,
                "client_name": client_name,
                "booking_type": "session_payment"
            }
        )
        
        return {
            "success": True,
            "session_id": session.id,
            "checkout_url": session.url,
            "payment_intent": session.payment_intent
        }
    except stripe.error.StripeError as e:
        return {
            "success": False,
            "error": str(e)
        }


def verify_connect_webhook_signature(payload: bytes, sig_header: str, webhook_secret: str) -> stripe.Event:
    """
    Vérifie la signature d'un webhook Stripe Connect.
    """
    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)


def handle_account_updated(event: stripe.Event) -> Dict[str, Any]:
    """
    Traite l'événement account.updated pour mettre à jour le statut du compte coach.
    """
    account = event.data.object
    
    requirements = account.requirements or {}
    
    return {
        "account_id": account.id,
        "email": account.email,
        "details_submitted": account.details_submitted,
        "charges_enabled": account.charges_enabled,
        "payouts_enabled": account.payouts_enabled,
        "currently_due": requirements.get("currently_due", []),
        "past_due": requirements.get("past_due", [])
    }

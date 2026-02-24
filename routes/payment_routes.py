"""
Routes Stripe : checkout, webhook, portal.
Les dependances (get_coach_for_checkout, etc.) sont injectees par main.py.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
import os

router = APIRouter(prefix="", tags=["stripe"])

def register_payment_routes(app, deps: dict):
    """Enregistre les routes Stripe sur l'app. deps = dict avec les fonctions requises."""
    get_coach_for_checkout = deps["get_coach_for_checkout"]
    _get_base_url = deps["_get_base_url"]
    _is_stripe_configured = deps["_is_stripe_configured"]
    create_or_get_customer = deps["create_or_get_customer"]
    create_checkout_session = deps["create_checkout_session"]
    update_coach_subscription = deps["update_coach_subscription"]
    log = deps.get("log")

    @app.post("/api/stripe/create-checkout-session")
    async def api_create_checkout_session(request: Request, user=Depends(get_coach_for_checkout)):
        """Cree une session Checkout Stripe pour l'abonnement."""
        if log:
            log.info("[Stripe] create_checkout_session appele")
        try:
            if not _is_stripe_configured():
                if log:
                    log.warning("[Stripe] Stripe non configure")
                return JSONResponse(
                    {"error": "Paiement temporairement indisponible. Les cles Stripe seront configurees prochainement.", "code": "STRIPE_NOT_CONFIGURED"},
                    status_code=503
                )
            base_url = _get_base_url(request)
            coach_email = user.get("email")
            if not coach_email:
                return JSONResponse({"error": "Email du coach introuvable"}, status_code=400)
            try:
                body = await request.json()
            except Exception:
                body = {}
            billing_period = body.get("billing_period", "monthly")
            coach_name = user.get("full_name", user.get("name", "Coach"))
            coach_id = user.get("id", coach_email)
            success_url = f"{base_url.rstrip('/')}/coach/subscription?success=true&session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{base_url.rstrip('/')}/coach/subscription?cancelled=true"
            stripe_price_id = (os.environ.get("STRIPE_PRICE_ID") or os.environ.get("STRIPE_MONTHLY_PRICE_ID") or "").strip()
            if stripe_price_id and stripe_price_id.startswith("price_"):
                import stripe
                from stripe_service import init_stripe
                init_stripe()
                session = stripe.checkout.Session.create(
                    mode="subscription",
                    customer_email=coach_email,
                    line_items=[{"price": stripe_price_id, "quantity": 1}],
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata={"coach_email": coach_email, "platform": "fitmatch"},
                )
            else:
                try:
                    customer = create_or_get_customer(coach_email, coach_name, coach_id)
                except Exception as customer_error:
                    if log:
                        log.error(f"[Stripe] create_or_get_customer: {customer_error}")
                    return JSONResponse({"error": f"Erreur client Stripe: {str(customer_error)}"}, status_code=500)
                update_coach_subscription(coach_email, stripe_customer_id=customer.id)
                session = create_checkout_session(
                    customer_id=customer.id,
                    success_url=success_url,
                    cancel_url=cancel_url,
                    coach_email=coach_email,
                    billing_period=billing_period
                )
            checkout_url = getattr(session, "url", None) if session else None
            if not checkout_url:
                return JSONResponse({"error": "Stripe n'a pas retourne d'URL"}, status_code=500)
            return JSONResponse({"url": checkout_url})
        except HTTPException:
            raise
        except Exception as e:
            if log:
                log.error(f"[Stripe] Erreur: {e}")
            import traceback
            traceback.print_exc()
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.post("/api/create_checkout_session")
    async def create_checkout_session_simple(request: Request):
        """Cree une session Stripe Checkout (mensuel 20€ ou annuel 200€)."""
        try:
            try:
                coach = await get_coach_for_checkout(request)
            except HTTPException:
                return JSONResponse({"error": "Coach non authentifie. Rechargez la page /coach/offre."}, status_code=401)
            if not coach:
                return JSONResponse({"error": "Coach non authentifie"}, status_code=401)
            coach_email = coach.get("email")
            if not _is_stripe_configured():
                return JSONResponse({"error": "Stripe non configure"}, status_code=503)
            try:
                body = await request.json()
            except Exception:
                body = {}
            billing_period = body.get("billing_period", "monthly")
            base_url = _get_base_url(request)
            success_url = f"{base_url.rstrip('/')}/coach/subscription?success=true&session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{base_url.rstrip('/')}/coach/subscription?cancelled=true"
            if billing_period == "annual":
                price_id = (os.environ.get("STRIPE_ANNUAL_PRICE_ID") or "").strip()
            else:
                price_id = (os.environ.get("STRIPE_PRICE_ID") or os.environ.get("STRIPE_MONTHLY_PRICE_ID") or "").strip()
            if price_id and price_id.startswith("price_"):
                import stripe
                from stripe_service import init_stripe
                init_stripe()
                session = stripe.checkout.Session.create(
                    mode="subscription",
                    customer_email=coach_email,
                    line_items=[{"price": price_id, "quantity": 1}],
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata={"coach_email": coach_email, "platform": "fitmatch"},
                )
            else:
                coach_id = coach.get("id") or coach.get("email", coach_email)
                customer = create_or_get_customer(coach_email, coach.get("full_name", "Coach"), str(coach_id))
                update_coach_subscription(coach_email, stripe_customer_id=customer.id)
                session = create_checkout_session(
                    customer_id=customer.id,
                    success_url=success_url,
                    cancel_url=cancel_url,
                    coach_email=coach_email,
                    billing_period=billing_period,
                )
            checkout_url = getattr(session, "url", None) if session else None
            if not checkout_url:
                return JSONResponse({"error": "Stripe n'a pas retourne d'URL"}, status_code=500)
            return JSONResponse({"url": checkout_url})
        except HTTPException:
            raise
        except Exception as e:
            if log:
                log.error(f"[Stripe] Erreur create_checkout_session: {e}")
            import traceback
            traceback.print_exc()
            return JSONResponse({"error": str(e)}, status_code=500)

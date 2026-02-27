"""
Facade pour Stripe Connect : utilise PostgreSQL (db_service) ou demo_users en fallback.
Permet au dashboard coach de fonctionner sans DATABASE_URL (ex: Replit dev, local).
"""
from typing import Optional, Dict
from logger import get_logger
log = get_logger()


def get_stripe_connect_info(email: str) -> Optional[Dict]:
    """Récupère les infos Stripe Connect (PostgreSQL ou demo_users)."""
    try:
        from db_service import get_stripe_connect_info as _db_get
        return _db_get(email)
    except Exception as e:
        log.debug(f"Stripe Connect info depuis DB échoué pour {email}: {e}")
    try:
        from utils import load_demo_users
        users = load_demo_users()
        ud = users.get(email, {})
        if not ud:
            return None
        acc_id = ud.get("stripe_connect_account_id")
        if not acc_id:
            return None
        return {
            "account_id": acc_id,
            "status": ud.get("stripe_connect_status", "not_connected"),
            "charges_enabled": bool(ud.get("stripe_connect_charges_enabled")),
            "payouts_enabled": bool(ud.get("stripe_connect_payouts_enabled")),
            "details_submitted": bool(ud.get("stripe_connect_details_submitted")),
        }
    except Exception as e:
        log.warning(f"Stripe Connect info fallback échoué pour {email}: {e}")
        return None


def update_stripe_connect_status(
    email: str,
    account_id: str = None,
    status: str = None,
    charges_enabled: bool = None,
    payouts_enabled: bool = None,
    details_submitted: bool = None
) -> bool:
    """Met à jour le statut Stripe Connect (PostgreSQL ou demo_users)."""
    try:
        from db_service import update_stripe_connect_status as _db_update
        ok = _db_update(
            email=email,
            account_id=account_id,
            status=status,
            charges_enabled=charges_enabled,
            payouts_enabled=payouts_enabled,
            details_submitted=details_submitted,
        )
        if ok:
            return True
    except Exception as e:
        log.debug(f"Stripe Connect update DB échoué pour {email}: {e}")
    try:
        from utils import load_demo_users, save_demo_user
        users = load_demo_users()
        ud = users.get(email, {})
        if not ud:
            return False
        if account_id is not None:
            ud["stripe_connect_account_id"] = account_id
        if status is not None:
            ud["stripe_connect_status"] = status
        if charges_enabled is not None:
            ud["stripe_connect_charges_enabled"] = charges_enabled
        if payouts_enabled is not None:
            ud["stripe_connect_payouts_enabled"] = payouts_enabled
        if details_submitted is not None:
            ud["stripe_connect_details_submitted"] = details_submitted
        return save_demo_user(email, ud)
    except Exception as e:
        log.warning(f"Stripe Connect update fallback échoué pour {email}: {e}")
        return False

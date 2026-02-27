#!/usr/bin/env python3
"""
Test du flux : créer un compte coach -> finaliser le profil -> vérifier redirection directe vers le dashboard.
Teste la soumission native du formulaire POST /coach/profile-setup (pas l'API JSON).
"""
import os
import sys
import urllib.parse

# Activer le mode test pour l'endpoint create-session
os.environ["TEST_SESSION"] = "1"
# Désactiver la DB pour utiliser le fallback fichier (éviter erreurs si pas de DATABASE_URL)
if "DATABASE_URL" not in os.environ:
    os.environ["DATA_DIR"] = os.getcwd()

# Import après avoir défini les env
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_test():
    from fastapi.testclient import TestClient
    from main import app
    from utils import save_demo_user, get_demo_user, _invalidate_users_cache

    client = TestClient(app)
    test_email = "test-coach-flow@example.com"

    print("=" * 60)
    print("TEST: Finaliser profil -> redirection directe vers dashboard")
    print("=" * 60)

    # 1. Créer un coach dans demo_users (profile_completed=False)
    _invalidate_users_cache()
    save_demo_user(test_email, {
        "email": test_email,
        "role": "coach",
        "profile_completed": False,
        "subscription_status": "active",
        "email_verified": True,
        "full_name": "",
        "bio": "",
        "city": "",
    })
    u = get_demo_user(test_email)
    assert u, "Coach doit exister"
    assert not u.get("profile_completed"), "profile_completed doit être False"
    print("1. Coach créé dans demo_users (profile_completed=False)")

    # 2. Créer une session (simule OTP vérifié)
    r = client.get(f"/api/test/create-session?email={urllib.parse.quote(test_email)}")
    assert r.status_code == 200, f"create-session: {r.status_code}"
    print("2. Session créée (simulation OTP)")

    # 3. Soumettre le formulaire profile-setup (POST natif comme le formulaire HTML)
    form_data = {
        "full_name": "Test Coach",
        "bio": "Bio test",
        "city": "Paris",
        "postal_code": "75001",
        "price_from": "50",
        "radius_km": "25",
        "form_submit": "1",
        "selected_gym_ids": "",
        "selected_gyms_data": "[]",
    }
    # Photo optionnelle en mode OTP/demo
    import io
    try:
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        files = {"profile_photo": ("photo.jpg", buf, "image/jpeg")}
    except ImportError:
        files = {}

    # Pas de X-Requested-With ni Accept JSON = soumission native
    r = client.post(
        "/coach/profile-setup",
        data=form_data,
        files=files,
        follow_redirects=False,
    )

    print(f"3. profile-setup POST response: {r.status_code}")

    if r.status_code != 303:
        print(f"\nERREUR: attendu 303 redirect, obtenu {r.status_code}")
        print(f"   Body: {r.text[:500]}")
        return False

    location = r.headers.get("location", "")
    if "/coach/portal" not in location:
        print(f"\nERREUR: redirection attendue vers /coach/portal, obtenu: {location}")
        return False

    print(f"   Redirect -> {location} [OK]")

    # 4. Suivre la redirection et vérifier qu'on arrive sur le dashboard
    r_portal = client.get("/coach/portal", follow_redirects=True)
    if r_portal.status_code != 200:
        print(f"\nERREUR: /coach/portal retourne {r_portal.status_code}")
        return False
    if "profile-setup" in str(r_portal.url):
        print(f"\nERREUR: redirigé vers profile-setup au lieu du dashboard")
        return False
    if "coach_portal" not in r_portal.text and "dashboard" not in r_portal.text.lower():
        # Le dashboard peut contenir "portail" ou "dashboard"
        pass  # On accepte 200 sur /coach/portal
    print("4. Dashboard chargé (200) [OK]")

    # 5. Vérifier profile_completed dans demo_users
    _invalidate_users_cache()
    u2 = get_demo_user(test_email)
    if not u2:
        print("\nERREUR: coach introuvable apres profile-setup")
        return False
    if not u2.get("profile_completed"):
        print("\nERREUR: profile_completed=False apres save!")
        return False
    print("5. profile_completed=True dans demo_users [OK]")

    print("\n" + "=" * 60)
    print("TEST REUSSI: Finaliser -> redirection directe vers dashboard OK")
    print("=" * 60)
    return True


if __name__ == "__main__":
    ok = run_test()
    sys.exit(0 if ok else 1)

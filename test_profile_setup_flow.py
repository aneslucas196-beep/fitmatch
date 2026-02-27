#!/usr/bin/env python3
"""
Test du flux : créer un compte coach -> finaliser le profil -> vérifier redirection vers le dashboard.
Lance le serveur en arrière-plan et exécute les requêtes.
"""
import os
import sys
import time
import subprocess
import urllib.request
import urllib.parse
import http.cookiejar

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
    from utils import save_demo_user, get_demo_user, load_demo_users, _invalidate_users_cache

    client = TestClient(app)
    test_email = "test-coach-flow@example.com"

    print("=" * 60)
    print("TEST: Flux profile-setup -> dashboard")
    print("=" * 60)

    # 1. Créer un coach dans demo_users (profile_completed=False)
    _invalidate_users_cache()
    save_demo_user(test_email, {
        "email": test_email,
        "role": "coach",
        "profile_completed": False,
        "subscription_status": "active",
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
    cookies = r.cookies
    print("2. Session créée (simulation OTP)")

    # 3. Soumettre le formulaire profile-setup
    form_data = {
        "full_name": "Test Coach",
        "bio": "Bio test",
        "city": "Paris",
        "postal_code": "75001",
        "price_from": "50",
        "radius_km": "25",
    }
    # Créer un fichier image minimal pour la photo (requis)
    import io
    from PIL import Image
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    files = {"profile_photo": ("photo.jpg", buf, "image/jpeg")}
    headers = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}

    r = client.post(
        "/api/coach/profile-setup",
        data=form_data,
        files=files,
        headers=headers,
        cookies=cookies,
    )

    print(f"3. profile-setup response: {r.status_code}")
    try:
        data = r.json()
        print(f"   Response: {data}")
    except Exception:
        print(f"   Body (raw): {r.text[:500]}")

    if r.status_code != 200:
        print(f"\nERREUR: profile-setup a retourne {r.status_code}")
        return False

    if not data.get("success"):
        print(f"\nERREUR: success=False, detail={data.get('detail', data.get('error'))}")
        return False

    redirect = data.get("redirect", "")
    if not redirect:
        print("\nERREUR: pas de redirect dans la reponse")
        return False

    print(f"3. profile-setup OK, redirect={redirect}")

    # 4. Vérifier que profile_completed est bien dans demo_users
    _invalidate_users_cache()
    u2 = get_demo_user(test_email)
    if not u2:
        print("\nERREUR: coach introuvable apres profile-setup")
        return False
    if not u2.get("profile_completed"):
        print("\nERREUR: profile_completed=False apres save!")
        return False
    print("4. profile_completed=True dans demo_users [OK]")

    # 5. Accéder au dashboard/portal - ne doit PAS rediriger vers profile-setup
    r_portal = client.get("/coach/portal", cookies=cookies, follow_redirects=False)
    if r_portal.status_code == 302:
        location = r_portal.headers.get("location", "")
        if "profile-setup" in location:
            print(f"\nERREUR: /coach/portal redirige vers profile-setup! ({location})")
            return False
    print(f"5. /coach/portal: {r_portal.status_code} (pas de redirection vers profile-setup) [OK]")

    print("\n" + "=" * 60)
    print("TEST REUSSI: Le flux profile-setup -> dashboard fonctionne correctement.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    ok = run_test()
    sys.exit(0 if ok else 1)

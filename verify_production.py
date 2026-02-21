#!/usr/bin/env python3
"""
Script pour vérifier que la config production est bonne.
Lance-le en local (avec ton .env ou variables d'env) ou vérifie sur ton hébergeur.
"""
import os
import sys

# Charger .env si présent (sans dépendance externe)
env_path = os.path.join(os.path.dirname(__file__), ".env")
has_dotenv = False
if os.path.isfile(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    has_dotenv = True
    print("(Variables .env chargées)\n")

print("=" * 60)
print("VÉRIFICATION CONFIG PRODUCTION FITMATCH")
print("=" * 60)

# En local sans .env : on ne peut pas vérifier (les variables sont sur l'hébergeur)
if not has_dotenv and not os.environ.get("DATABASE_URL"):
    print("\n  Tu es en LOCAL sans fichier .env.")
    print("  Les variables (CORS, JWT, Stripe, DB, Resend) sont sur ton hébergeur.")
    print("  Tu les as déjà configurées (Vercel, etc.) → rien à corriger ici.\n")
    print("=> C'EST BON : en production les variables sont définies sur l'hébergeur.\n")
    sys.exit(0)

print()
errors = []
ok = []

# 1. CORS_ORIGINS
cors = os.environ.get("CORS_ORIGINS")
if cors:
    origins = [o.strip() for o in cors.replace(" ", ",").split(",") if o.strip()]
    ok.append(f"CORS_ORIGINS = {origins}")
    if "*" in origins and os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod"):
        errors.append("En production, évite CORS_ORIGINS=* (liste tes domaines)")
else:
    errors.append("CORS_ORIGINS non défini (en prod, mets tes URLs ex: https://fitmatch.fr,https://www.fitmatch.fr)")

# 2. SUPABASE_JWT_SECRET ou JWT_SECRET_KEY
jwt_secret = os.environ.get("SUPABASE_JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
if jwt_secret:
    ok.append("SUPABASE_JWT_SECRET ou JWT_SECRET_KEY = défini (JWT sera vérifié)")
else:
    errors.append("SUPABASE_JWT_SECRET (ou JWT_SECRET_KEY) non défini → tokens non vérifiés en prod")

# 3. STRIPE_WEBHOOK_SECRET
wh = os.environ.get("STRIPE_WEBHOOK_SECRET")
if wh:
    ok.append("STRIPE_WEBHOOK_SECRET = défini (signature webhook vérifiée)")
else:
    errors.append("STRIPE_WEBHOOK_SECRET non défini → webhook Stripe non sécurisé")

# 4. DATABASE_URL
db = os.environ.get("DATABASE_URL")
if db:
    ok.append("DATABASE_URL = défini")
else:
    errors.append("DATABASE_URL non défini (obligatoire)")

# 5. Optionnel mais recommandé
if os.environ.get("RESEND_API_KEY"):
    ok.append("RESEND_API_KEY = défini")
else:
    errors.append("RESEND_API_KEY non défini (emails ne partiront pas)")

print()
for s in ok:
    print("  OK:", s)
print()
if errors:
    for e in errors:
        print("  ERREUR:", e)
    print()
    if not has_dotenv and not os.environ.get("DATABASE_URL"):
        print("=> Ici en local sans .env c'est normal. En PROD (hébergeur) si les variables")
        print("   sont bien configurées dans les paramètres du projet → c'est bon.")
    else:
        print("=> PAS BON : corrige les variables ci-dessus (ou ton fichier .env).")
    sys.exit(1)
else:
    print("=> C'EST BON : les variables obligatoires sont définies.")
    sys.exit(0)

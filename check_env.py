#!/usr/bin/env python3
"""Check that required env vars are set. Run after filling .env (or set vars)."""
import os
import sys

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

REQUIRED = [
    "DATABASE_URL",
    "RESEND_API_KEY",
    "SENDER_EMAIL",
    "STRIPE_SECRET_KEY",
    "STRIPE_PUBLIC_KEY",
    "STRIPE_WEBHOOK_SECRET",
]

OPTIONAL = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SUPABASE_JWT_SECRET",
    "GOOGLE_MAPS_API_KEY",
    "CORS_ORIGINS",
    "SITE_URL",
    "JWT_SECRET_KEY",
]

def main():
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    present_required = [k for k in REQUIRED if os.environ.get(k)]
    present_optional = [k for k in OPTIONAL if os.environ.get(k)]

    print("Required:")
    for k in REQUIRED:
        val = os.environ.get(k)
        status = "OK" if val else "MISSING"
        if val and len(val) > 20:
            val = val[:12] + "..." + val[-4:]
        print(f"  {k}: {status}" + (f" ({val})" if val else ""))

    print("\nOptional (set if you use them):")
    for k in OPTIONAL:
        val = os.environ.get(k)
        status = "set" if val else "-"
        print(f"  {k}: {status}")

    if missing:
        print("\nMissing required:", ", ".join(missing))
        print("Fill .env (copy from .env.example) and add these, then run again.")
        return 1
    print("\nAll required variables are set. You can run: python start_server.py")
    print("For production: follow DEPLOY_RENDER_5_STEPS.md")
    return 0

if __name__ == "__main__":
    sys.exit(main())

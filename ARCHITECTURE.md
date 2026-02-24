# Architecture FitMatch

## Vue d'ensemble

FitMatch est une plateforme de mise en relation entre coachs sportifs et clients, construite avec FastAPI.

## Diagramme d'architecture

```mermaid
flowchart TB
    subgraph Client
        Browser[ navigateur ]
    end

    subgraph FitMatch["FitMatch (FastAPI)"]
        subgraph Routes
            Auth[auth_routes]
            Payment[payment_routes]
            System[system_routes]
            Pages[pages_routes]
            Main[main.py routes]
        end

        subgraph Services
            DB[db_service]
            Stripe[stripe_service]
            Resend[resend_service]
            Supabase[supabase_auth]
        end

        subgraph Utils
            Utils[utils]
            AuthUtils[auth_utils]
        end

        Routes --> Services
        Routes --> Utils
    end

    subgraph External["Services externes"]
        PostgreSQL[(PostgreSQL)]
        StripeAPI[Stripe API]
        ResendAPI[Resend API]
        SupabaseAPI[Supabase]
        GooglePlaces[Google Places]
    end

    Browser --> FitMatch
    DB --> PostgreSQL
    Stripe --> StripeAPI
    Resend --> ResendAPI
    Supabase --> SupabaseAPI
    Utils --> GooglePlaces
```

## Flux principaux

### Inscription client/coach

```
Client → /signup → validation → OTP (Resend) → /verify-otp → compte créé
Coach  → /coach/signup → Supabase ou démo → profil complété
```

### Réservation

```
Client → recherche coach/salle → /coach/{id}/book → formulaire
      → /api/confirm-booking → email coach → coach accepte/refuse
      → email confirmation (Resend)
```

### Paiement coach (Stripe)

```
Coach → /coach/subscription → /api/stripe/create-checkout-session
     → Stripe Checkout → webhook → abonnement actif
```

## Sécurité

- **CSRF** : tokens dans cookie + formulaire
- **Auth** : sessions HMAC-SHA256, JWT Supabase
- **CSP** : Content-Security-Policy avec nonce
- **Rate limiting** : slowapi sur login, signup

## Déploiement (Render)

- **Web** : service principal (uvicorn)
- **Worker** : rappels email (process_due_reminders)
- **DB** : PostgreSQL (Supabase ou Render)

# FitMatch

Plateforme de mise en relation **clients** et **coachs sportifs** : recherche par ville/salle, réservation de séances, abonnements coach (Stripe), paiement en ligne des séances (Stripe Connect), rappels et emails (Resend).

## Prérequis

- **Python 3.10+**
- **PostgreSQL** (requis en production)
- Comptes : **Stripe**, **Resend**, **Supabase** (optionnel), **Google Maps/Places** (optionnel)

## Installation

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Variables d'environnement

Copier `.env.example` vers `.env` et renseigner les valeurs. Principales variables :

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `DATABASE_URL` | **Oui** | URL PostgreSQL (ex: `postgresql://user:pass@localhost:5432/fitmatch`) |
| `STRIPE_SECRET_KEY` | Oui (paiements) | Clé secrète Stripe |
| `STRIPE_WEBHOOK_SECRET` | **Oui en prod** | Secret du webhook Stripe (vérification signature) |
| `RESEND_API_KEY` | Oui (emails) | Clé API Resend |
| `SENDER_EMAIL` | Oui (emails) | Email expéditeur (ex: `contact@fitmatch.fr`) |
| `SUPABASE_URL` / `SUPABASE_KEY` | Optionnel | Auth Supabase |
| `SUPABASE_JWT_SECRET` | Recommandé en prod | JWT Secret (Supabase Project Settings > API) pour vérifier les tokens |
| `CORS_ORIGINS` | En prod | Origines autorisées (ex: `https://fitmatch.fr,https://www.fitmatch.fr`). Non défini = `*` |
| `GOOGLE_MAPS_API_KEY` | Optionnel | Carte et recherche de salles |

Voir **`.env.example`** pour la liste complète.

## Lancer l'application

```bash
uvicorn main:app --host 0.0.0.0 --port 5000
```

Ou :

```bash
python main.py
```

- **App** : http://localhost:5000  
- **Documentation API** : http://localhost:5000/docs  
- **ReDoc** : http://localhost:5000/redoc  

## Checklist pré-production

- [ ] **PostgreSQL** : `DATABASE_URL` configuré (l’app refuse de démarrer sans)
- [ ] **Stripe**
  - [ ] Webhook configuré : URL `https://votre-domaine.com/api/stripe/webhook`
  - [ ] Événements : `checkout.session.completed`, `invoice.payment_succeeded`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`
  - [ ] `STRIPE_WEBHOOK_SECRET` défini (obligatoire pour la vérification de signature)
- [ ] **Emails (Resend)** : `RESEND_API_KEY` et `SENDER_EMAIL` (ex: `contact@fitmatch.fr`)
- [ ] **CORS** : `CORS_ORIGINS` défini avec les domaines autorisés (ex: `https://fitmatch.fr,https://www.fitmatch.fr`)
- [ ] **JWT** : `SUPABASE_JWT_SECRET` (ou `JWT_SECRET_KEY`) pour vérifier les tokens en production
- [ ] **Google Maps** : `GOOGLE_MAPS_API_KEY` si vous utilisez la carte / recherche de salles

## Structure

- **`main.py`** : routes FastAPI, auth, réservations, Stripe, pages
- **`config.py`** : configuration centralisée (env)
- **`utils.py`** : helpers, géoloc, stockage utilisateurs (PostgreSQL via `db_service`)
- **`db_service.py`** : accès PostgreSQL (utilisateurs, Stripe Connect)
- **`stripe_service.py`** / **`stripe_connect_service.py`** : abonnements et paiements séances
- **`resend_service.py`** : envoi d’emails (OTP, confirmations, rappels, etc.)
- **`i18n_service.py`** : traductions (fr, en, es, ar, de, it, pt)
- **`templates/`** : Jinja2 (pages HTML)
- **`translations/`** : fichiers JSON par langue
- **`migrations/`** : scripts SQL (voir `migrations/README.md`)

## Tests

```bash
pytest tests/ -v
```

## Licence

Propriétaire – FitMatch.

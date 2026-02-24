# FitMatch

Plateforme de mise en relation **clients** et **coachs sportifs**

**→ [You send me the keys, I do the rest](SEND_ME_THIS.md)** · **→ [Comment lancer le site (local ou en ligne) ?](COMMENT_LANCER_LE_SITE.md)** : recherche par ville/salle, réservation de séances, abonnements coach (Stripe), paiement en ligne des séances (Stripe Connect), rappels et emails (Resend).

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

**Développement** : `pip install -r requirements-dev.txt` pour black, isort, pytest-cov, pip-audit.

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

## Documentation

- **[CONTRIBUTING.md](CONTRIBUTING.md)** : guide de contribution (tests, formatage, PR)
- **[ARCHITECTURE.md](ARCHITECTURE.md)** : diagrammes d'architecture, flux, composants

## Lancer l'application (tout en un : web + rappels 24/7)

Une seule commande lance le site **et** l’envoi des rappels (24h et 2h avant le RDV) en arrière-plan :

```bash
python start_server.py
```

Ou :

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
- **Rappels** : exécutés automatiquement toutes les 60 secondes (variable `REMINDERS_INTERVAL_SEC` pour changer). Aucun cron ni worker séparé nécessaire.

**Serveur 24/7** : scripts `start.sh` / `start.bat` et service systemd → voir **[DEPLOIEMENT_24H.md](DEPLOIEMENT_24H.md)**.

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

## Déploiement sur Render (Web + Worker)

Le fichier **`render.yaml`** définit deux services : **fitmatch-web** (Web Service FastAPI) et **fitmatch-reminders-worker** (rappels 24h/2h en boucle). Python 3.12 est forcé (`.python-version` + `PYTHON_VERSION`).

### À faire sur Render (toi)

1. **Connexion** : [dashboard.render.com](https://dashboard.render.com) → connecte ton repo GitHub (FitMatch).
2. **Blueprint** : dans le repo, le fichier `render.yaml` définit un service de type `worker`. Render le détecte si tu crées un **Blueprint** (New → Blueprint) et tu pointes vers ce repo.
3. **Ou service manuel** : New → Background Worker → connecte le repo, puis :
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `python worker.py`
4. **Variables d’environnement** (obligatoires pour le worker) :  
   Dans le dashboard Render → ton service **fitmatch-reminders-worker** → onglet **Environment** → ajoute les mêmes variables que pour l’app (elles sont lues par `main.py` / `resend_service`) :
   - `DATABASE_URL` (PostgreSQL)
   - `RESEND_API_KEY`
   - `SENDER_EMAIL`
   - Optionnel : `REMINDERS_INTERVAL_SEC` (défaut 60), `SCHEDULED_REMINDERS_FILE` (défaut `scheduled_reminders.json`)

   **Python** : le fichier `.python-version` (3.12.8) force Render à utiliser Python 3.12. Ne pas utiliser 3.14 (build pydantic-core échoue).

Une fois déployé, le worker tourne H24 et envoie les rappels automatiquement (24h et 2h avant chaque réservation).

## Structure

- **`main.py`** : routes FastAPI, auth, réservations, Stripe, pages
- **`worker.py`** : worker H24 pour les rappels (process_due_reminders en boucle ; déploiement Render)
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

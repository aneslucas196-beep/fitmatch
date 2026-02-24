# Audit technique complet – FitMatch

*Date : février 2025*
*Dernière mise à jour : corrections appliquées*

## Corrections appliquées (post-audit)

- **Sécurité** : Token de session HMAC-SHA256 (remplace MD5) via `auth_utils.py`
- **CORS** : En production, refus de `*` ; fallback sur SITE_URL si CORS_ORIGINS non défini
- **Pool DB** : `db_service.py` utilise déjà ThreadedConnectionPool
- **SEO** : `/robots.txt` et `/sitemap.xml` dynamiques
- **Open Graph** : Meta tags og: et twitter: dans `base.html`
- **Retry** : Retry (3 tentatives) sur envoi OTP Resend

---

## 1. Architecture

### Stack technique
| Composant | Technologie |
|-----------|-------------|
| Backend | FastAPI (Python 3.12) |
| Templates | Jinja2 |
| Base de données | PostgreSQL (Supabase) |
| Stockage images | Supabase Storage |
| Paiements | Stripe |
| Emails | Resend |
| Géolocalisation | Google Maps / Places API |
| Déploiement | Render (web + worker) |

### Points positifs
- Architecture modulaire : `stripe_service.py`, `resend_service.py`, `db_service.py`, `utils.py`
- Configuration centralisée dans `config.py`
- i18n : 7 langues (fr, en, es, ar, de, it, pt)
- Endpoint `/health` pour monitoring

### Problèmes
- **main.py** (~7600 lignes) : fichier monolithique, difficile à maintenir
- Logique métier mélangée avec les routes
- Pas de tests unitaires visibles

---

## 2. Sécurité

### Points positifs
- Protection CSRF (tokens générés et vérifiés)
- Rate limiting (slowapi) sur login, OTP, reset password
- Headers de sécurité : CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- Mots de passe hashés (bcrypt)
- Cookies : HttpOnly, Secure en prod, SameSite=Lax
- Protection SQL injection (paramètres `%s` dans db_service)
- Validation d’images côté serveur (Pillow)
- Sanitisation des IDs (path traversal)

### Vulnérabilités à traiter

| Priorité | Problème | Recommandation |
|----------|----------|----------------|
| Haute | Token de session basé sur MD5 + email | Remplacer par `secrets.token_urlsafe(32)` |
| Haute | CSP avec `'unsafe-inline'` | Utiliser des nonces ou retirer si possible |
| Moyenne | CORS `["*"]` en dev | Forcer des origines explicites en production |
| Moyenne | Fallback mot de passe en clair (compatibilité) | Supprimer progressivement |

---

## 3. Performance

### Problèmes
- Pas de pool de connexions PostgreSQL (connexion par requête)
- Pas de cache (Redis) pour données fréquentes
- `load_users_from_db()` : `SELECT *` sans limite
- Pas de pagination sur certaines listes (coachs, réservations)
- Requêtes N+1 possibles dans `get_coaches_by_gym_id`

### Recommandations
1. Pool de connexions (psycopg2.pool)
2. Cache Redis pour coachs, salles
3. Pagination sur les listes
4. Index sur `email`, `role`, `subscription_status`
5. `SELECT` ciblé au lieu de `SELECT *`

---

## 4. Qualité du code

### Problèmes
- Duplication : auth Supabase vs mode démo
- Gestion d’erreurs : beaucoup de `print()` au lieu de logging
- Pas de Repository Pattern
- Pas de DTO Pydantic pour validation stricte

### Recommandations
1. Extraire la logique dans des services
2. Logging structuré (structlog ou logging)
3. Modèles Pydantic pour validation
4. Découper `main.py` en modules (routes/auth, routes/coach, etc.)

---

## 5. Base de données

### Schéma actuel
- Table `users` avec colonnes TEXT (JSON stocké en texte)
- Pas de normalisation (specialties, selected_gyms_data en JSON)

### Problèmes
- Stockage JSON en TEXT (pas de validation DB)
- Pas de migrations versionnées (Alembic)
- Pas de transactions explicites pour opérations multiples

### Recommandations
1. JSONB PostgreSQL au lieu de TEXT
2. Tables séparées pour specialties, bookings, gym_relations
3. Alembic pour migrations
4. Transactions pour opérations atomiques

---

## 6. APIs externes

| Service | Points positifs | Problèmes |
|---------|-----------------|-----------|
| Stripe | Vérification signature webhook | Pas de retry, peu de logs |
| Supabase | RLS activé | Gestion d’erreurs variable |
| Resend | Envoi fonctionnel | Pas de queue, pas de retry |
| Google Maps | Timeout géré | Pas de cache, pas de fallback |

### Recommandations
1. Retry avec backoff exponentiel
2. Logs pour tous les appels externes
3. Queue pour emails (Celery/RQ ou équivalent)
4. Cache pour résultats Google Places

---

## 7. Frontend

### Points positifs
- i18n intégré
- Design responsive
- Templates Jinja2 structurés

### Problèmes
- Pas de meta Open Graph / Twitter Cards
- Pas de schema.org (JSON-LD)
- CDN sans SRI (Subresource Integrity)
- Accessibilité limitée (ARIA, navigation clavier)

---

## 8. SEO

### Manques
- Pas de `robots.txt`
- Pas de `sitemap.xml`
- Meta descriptions génériques
- Pas de canonical URLs
- Pas de structured data (JSON-LD)

### Recommandations
1. Créer `robots.txt`
2. Générer `sitemap.xml` dynamiquement
3. Meta descriptions par page
4. JSON-LD (LocalBusiness, Person)

---

## 9. Déploiement (Render)

### Points positifs
- `render.yaml` configuré (web + worker)
- Variables d’environnement documentées
- `run_render.py` pour logs d’erreurs

### Problèmes
- Pas de validation de toutes les variables au démarrage
- Pas de monitoring/alerting (Sentry, etc.)

---

## 10. Plan d’action priorisé

### Critique (immédiat)
1. Remplacer le token de session MD5 par un token aléatoire sécurisé
2. Vérifier que `CORS_ORIGINS` est bien défini en production (pas `*`)

### Haute priorité (1–2 semaines)
1. Pool de connexions DB
2. Logging structuré
3. Pagination sur les listes
4. `robots.txt` et `sitemap.xml`
5. Meta tags Open Graph

### Moyenne priorité (1 mois)
1. Refactoriser `main.py` en modules
2. Cache Redis
3. Retry pour APIs externes
4. Améliorer accessibilité
5. Monitoring (Sentry)

### Basse priorité (continu)
1. Tests unitaires
2. Normalisation DB
3. Optimisation requêtes
4. Amélioration UX (loading, erreurs)

---

## Annexes

### Variables d’environnement critiques (production)
- `DATABASE_URL` – requis
- `SITE_URL` – requis (ex: https://fitmatch.fr)
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLIC_KEY`, `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID` ou `STRIPE_MONTHLY_PRICE_ID` (20€)
- `STRIPE_ANNUAL_PRICE_ID` (200€)
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`
- `SUPABASE_JWT_SECRET` ou `JWT_SECRET_KEY` (validation tokens)
- `RESEND_API_KEY`, `SENDER_EMAIL`
- `CORS_ORIGINS` (ex: https://fitmatch.fr,https://www.fitmatch.fr)

### Endpoints principaux
- `GET /health` – health check
- `POST /api/create_checkout_session` – Stripe Checkout (mensuel/annuel)
- `POST /api/stripe/create-checkout-session` – idem
- Webhooks Stripe configurés

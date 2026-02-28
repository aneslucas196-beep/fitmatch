# Audit complet FitMatch - Février 2025

## 1. Structure du projet

| Composant | Fichiers | Description |
|-----------|----------|-------------|
| **Backend** | `main.py` | Application FastAPI principale |
| **Base de données** | `db_service.py`, `db_pool.py` | PostgreSQL/Supabase |
| **Utilitaires** | `utils.py`, `auth_utils.py` | OTP, géocodage, utilisateurs |
| **i18n** | `i18n_service.py` | Traductions multilingues |
| **Templates** | `templates/*.html` | Pages HTML (coach_portal, booking, etc.) |
| **Traductions** | `translations/*.json` | fr, en, ar, de, es, it, pt |
| **Migrations** | `migrations/*.sql` | Schéma base de données |

---

## 2. Bugs corrigés

### 2.1 `working_hours` non persisté en base
- **Fichier** : `db_service.py`
- **Correction** : Ajout de la colonne `working_hours` dans `save_user_to_db()`
- **Migration** : `migrations/003_add_working_hours.sql`
- **Fallback** : Si la colonne n'existe pas, sauvegarde sans working_hours + avertissement

### 2.2 `set_coach_working_hours` utilisait `save_demo_users`
- **Fichier** : `main.py`
- **Correction** : Utilisation de `save_demo_user()` pour ne sauvegarder que le coach modifié

### 2.3 `working_hours` stocké en JSON (string) en DB
- **Fichier** : `main.py`
- **Correction** : Parsing JSON dans `get_coach_working_hours` et dans la logique de disponibilités

### 2.4 Lien de partage (Copier le lien)
- **Fichier** : `templates/coach_portal.html`
- **Correction** : `shareUrl` utilise `window.location.origin` en priorité ; `preventDefault`/`stopPropagation` sur le bouton ; fallback si input vide

### 2.5 Boutons partage social
- **Fichier** : `templates/coach_portal.html`
- **Correction** : `preventDefault` et `stopPropagation` pour rester sur le dashboard

---

## 3. APIs Coach

| Endpoint | Méthode | Auth | Description |
|----------|---------|------|-------------|
| `/api/coach/working-hours` | GET | Non | Récupère les horaires |
| `/api/coach/working-hours` | POST | `require_coach_session_or_cookie` | Sauvegarde les horaires |
| `/api/coach/session-duration` | GET | Non | Récupère la durée de séance |
| `/api/coach/session-duration` | POST | `require_coach_session_or_cookie` | Sauvegarde la durée |
| `/api/coach/payment-mode` | POST | `require_coach_session_or_cookie` | Mode paiement |
| `/api/coach/unavailability` | GET/POST | `require_coach_session_or_cookie` | Indisponibilités |
| `/api/coach/stripe-connect/*` | GET/POST | `require_coach_session_or_cookie` | Stripe Connect |

---

## 4. Langues et traductions

- **fr.json** : Français (complet)
- **en.json** : Anglais (complet)
- **ar.json, de.json, es.json, it.json, pt.json** : Autres langues
- **Détection** : Cookie `locale`, headers Accept-Language, route `/set-language/{locale}`

---

## 5. Base de données

### Colonnes utilisateurs
- `working_hours` (TEXT, JSON) : Horaires personnalisés par jour
- `session_duration` (INTEGER) : Durée des séances en minutes
- `payment_mode` : `disabled` ou `required`
- `unavailable_days`, `unavailable_slots` : Indisponibilités

### Migration Supabase
Si la table `users` existe déjà, exécuter dans le SQL Editor :
```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS working_hours TEXT;
```

---

## 6. Dashboard coach - Boutons

| Bouton | Action |
|--------|--------|
| Copier le lien | Copie le lien de réservation, reste sur la page |
| WhatsApp / Instagram / Facebook / X | Partage sur le réseau (nouvel onglet) |
| Voir mon profil public | Ouvre le profil dans un nouvel onglet |
| 30 min / 1h / 1h30 / 2h | Change la durée de séance |
| + Disponibilité | Ouvre la modale horaires |
| Mode de paiement | Désactivé / Obligatoire (Stripe Connect) |
| Semaine / Mois | Vue calendrier |
| Précédent / Suivant | Navigation calendrier |

---

## 7. Variables d'environnement (Render)

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `DATABASE_URL` | Oui | URL PostgreSQL Supabase |
| `SITE_URL` | Oui | URL du site (ex: https://fitmatch.fr) |
| `STRIPE_SECRET_KEY` | Oui | Clé secrète Stripe |
| `STRIPE_PUBLISHABLE_KEY` | Oui | Clé publique Stripe |
| `STRIPE_WEBHOOK_SECRET` | Oui | Secret webhook Stripe |
| `RESEND_API_KEY` | Oui | API Resend (emails) |
| `SUPABASE_URL` | Oui | URL Supabase |
| `SUPABASE_SERVICE_KEY` | Oui | Clé service Supabase |
| `CORS_ORIGINS` | Oui | Origines CORS autorisées |
| `ENVIRONMENT` | Non | `production` ou `development` |

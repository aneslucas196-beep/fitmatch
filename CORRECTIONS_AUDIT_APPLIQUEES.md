# Corrections audit appliquées

## 1. Cache load_demo_users (CRITIQUE)

- **Problème** : `load_demo_users()` appelé 50+ fois par requête en production
- **Solution** : Cache avec TTL en production (60s par défaut)
- **Fichiers** : `utils.py`
- **Variables** : `USERS_CACHE_TTL_SEC` (0 = désactivé), `ENVIRONMENT=production`
- **Invalidation** : Automatique après `save_demo_user`, `save_demo_users`, `remove_demo_user`

## 2. Logging structuré

- **Problème** : `print()` partout, logs non structurés
- **Solution** : Remplacement par `log.info()`, `log.warning()`, `log.error()` (logger.py)
- **Fichiers** : `main.py`, `utils.py`
- **Variable** : `LOG_LEVEL` (INFO, DEBUG, WARNING, ERROR)

## 3. Pagination

- **Endpoints** :
  - `/api/coaches` : limit, offset (déjà présents)
  - `/api/client/bookings` : limit (50), offset (0)
  - `/api/gyms` : limit, offset (déjà présents)

## 4. CSP améliorée

- **Ajouts** :
  - `connect-src` : Stripe, Supabase
  - `frame-src` : Stripe (checkout iframes)
  - `img-src` : blob:
- **Fichier** : `main.py` (`_get_csp_header`)

## 5. Non appliqué (complexité)

- **N+1 queries** : Réduction nécessiterait une table `bookings` dédiée
- **Découpage main.py** : Refactorisation majeure, reportée

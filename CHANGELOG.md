# Changelog FitMatch

Toutes les modifications notables du projet sont documentées ici.

## [1.0.0] - 2026-02

### Ajouté

- Plateforme coachs/clients (FastAPI)
- Intégration Stripe (abonnements, checkout)
- Intégration Supabase (auth, DB)
- Intégration Resend (emails OTP, confirmations)
- Routes modulaires (auth, payment, system, pages)
- Support i18n (7 langues)
- Cache utilisateurs avec TTL
- Optimisations N+1 (batch gyms, coaches)
- Pagination sur les endpoints API
- Tests (auth, security, health, API)
- Documentation (README, CONTRIBUTING, ARCHITECTURE)
- pyproject.toml (black, isort)
- requirements-dev.txt

### Sécurité

- CSRF sur les formulaires
- CSP avec nonce
- Rate limiting (login, signup)
- verify_password sans fallback en clair
- Tokens session HMAC-SHA256

### Corrigé

- Fallback mot de passe dangereux supprimé
- print() remplacés par log
- Démarrage sans DATABASE_URL en local
- Duplicate register_coach_routes supprimé

### Refactorisation

- **services/coach_service.py** : logique métier coaches extraite
- **routes/coach_routes.py** : endpoint /api/coaches extrait de main.py
- **monitoring.py** : configuration Sentry optionnelle (SENTRY_DSN)
- **tests/test_coach_service.py** : tests unitaires du service coach

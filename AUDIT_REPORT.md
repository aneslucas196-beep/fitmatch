# Rapport d'audit FitMatch — Production Replit

**Date :** Audit complet du projet  
**Objectif :** Vérifier la préparation à la mise en production (Replit, forte charge).

---

## 1. Synthèse

| Domaine              | État  | Commentaire principal                                      |
|----------------------|-------|-------------------------------------------------------------|
| Backend / routes     | ✅ Bon | Health, rate limits, auth sur routes sensibles             |
| Sécurité             | ⚠️ À renforcer | Pas de CSRF ; APIs coach/bookings/messages non protégées |
| Paiements / Stripe   | ✅ Bon | Webhook sécurisé en prod, Connect utilisé correctement    |
| Base de données      | ✅ Bon | Paramétrage SQL, fallback fichier si DB absente           |
| Templates / i18n     | ✅ Bon | FAQ, liens légaux ; `|safe` limité au contenu traduit     |
| Config / déploiement | ✅ Bon | check_env.py, config centralisée, CORS, security headers   |

---

## 2. Points positifs

### 2.1 Backend
- **Health check** : `GET /health` avec statut DB (ok/skip/error) pour monitoring Replit.
- **Rate limiting** (SlowAPI) sur : signup 8/min, login 10/min, coach-login 10/min, forgot-password 5/min, verify-email 10/min, resend-otp 3/min, confirm-booking 30/min.
- **Headers de sécurité** : X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy.
- **Stripe webhook** : en production (SITE_URL défini), refus si `STRIPE_WEBHOOK_SECRET` absent ; signature vérifiée quand le secret est présent.
- **Auth** : `get_current_user` (cookie session_token), `require_auth`, `require_coach_role`, `require_active_subscription` ; routes coach protégées (portal, profile-setup, Stripe Connect, respond booking).
- **CORS** : configuré via `config.Settings.CORS_ORIGINS` (variable `CORS_ORIGINS`).

### 2.2 Données
- **PostgreSQL** : requêtes paramétrées (`%s`) dans `db_service.py` ; pas de concaténation SQL.
- **Fallback** : si `DATABASE_URL` absent ou erreur, utilisation de `demo_users` (fichier) pour ne pas bloquer.
- **Schéma** : `SUPABASE_CREATE_TABLE.md` documente la table `users` avec colonnes Stripe Connect.

### 2.3 Paiements
- Création de session Stripe Checkout pour séances (Connect) avec `booking_id` et métadonnées.
- Webhook gère `checkout.session.completed` (session_payment + abonnements) et met à jour les réservations / envoie emails.

### 2.4 Frontend / i18n
- Page **FAQ** dédiée (`/faq`) + lien « Voir toute la FAQ » sur l’accueil (clé `legal.faq_page` en FR/EN).
- Langues supportées : fr, en, es, ar, de, it, pt ; détection par query, cookie, Accept-Language.
- Contenu FAQ affiché avec `|safe` provient des fichiers de traduction (pas d’entrée utilisateur brute).

### 2.5 Déploiement
- `check_env.py` liste les variables requises (DATABASE_URL, RESEND, Stripe, etc.).
- `config.py` charge `.env`, expose `Settings` (CORS, JWT, SITE_URL, ENVIRONMENT).
- `start_server.py` : uvicorn sur `0.0.0.0` et `PORT` d’environnement.

---

## 3. Vulnérabilités et risques

### 3.1 Critique / Haute priorité

1. **APIs coach/bookings sans auth**
   - **`GET /api/coach/bookings?coach_email=...`** : retourne toutes les réservations d’un coach sans vérifier la session. N’importe qui peut lister les réservations en devinant un email coach.
   - **Recommandation** : exiger `Depends(require_coach_role)` et n’autoriser que les réservations du coach connecté (comparer `user["email"]` à `coach_email` ou ignorer le paramètre et utiliser uniquement la session).

2. **`GET /api/booking/{booking_id}`**
   - Retourne les détails d’une réservation (client, coach, date, etc.) sans authentification. Fuite d’informations si l’ID est devinable ou fuité.
   - **Recommandation** : exiger une session (client ou coach) et vérifier que la réservation appartient à l’utilisateur (client_email ou coach_email).

3. **Messages sans auth**
   - **`POST /api/messages/send`** et **`GET /api/messages/{booking_id}`**, **`GET /api/conversations`** : aucun contrôle de session. On peut envoyer des messages en se faisant passer pour un client/coach et lire des conversations en passant `client_email`/`coach_email`/`booking_id`.
   - **Recommandation** : exiger une session (client ou coach) et vérifier que `client_email` ou `coach_email` correspond à l’utilisateur connecté ; pour les messages, lier la conversation au booking et à la session.

### 3.2 Moyenne priorité

4. **`POST /api/cancel-booking`**
   - Pas de rate limit. Un acteur malveillant peut annuler en masse en rejouant des requêtes (avec les infos de la réservation).
   - **Recommandation** : ajouter `@limiter.limit("20/minute")` (ou similaire) et, idéalement, vérifier que l’appelant est le client ou le coach de la réservation (session ou token).

5. **CSRF**
   - Aucune protection CSRF sur les formulaires (POST signup, login, coach-login, réservation, etc.). En production, avec des cookies de session, un site tiers peut forger des requêtes si l’utilisateur est connecté.
   - **Recommandation** : tokens CSRF (cookie + champ caché ou header) pour les POST sensibles, ou au minimum pour login/signup/coach-login et réservation.

6. **Route `/images/{image_path:path}`**
   - Le handler est un simple `pass` ; la route ne renvoie rien (comportement indéfini côté FastAPI).
   - **Recommandation** : renvoyer explicitement 404 (ou supprimer la route si les images passent uniquement par Supabase Storage).

### 3.3 Basse priorité

7. **Validation des entrées**
   - Emails : `.lower().strip()` partout, pas de format strict (EmailStr Pydantic) sur tous les endpoints.
   - **Recommandation** : utiliser `EmailStr` dans les modèles Pydantic pour les champs email où c’est pertinent.

8. **CSP**
   - Pas de Content-Security-Policy. Risque d’injection de script si un vecteur (ex. traduction ou champ mal échappé) apparaît plus tard.
   - **Recommandation** : ajouter un en-tête CSP progressif (report-only puis enforce) pour limiter les sources de script.

9. **Rate limit sur `POST /api/signup-reservation`**
   - Pas de limite explicite ; proche du signup classique (lui limité à 8/min).
   - **Recommandation** : appliquer la même limite (ou 5/min) pour éviter les inscriptions abusives depuis cette route.

---

## 4. Dépendances et config

- **requirements.txt** : versions fixées (FastAPI, Stripe, Resend, bcrypt, slowapi, etc.) — correct pour la reprod.
- **Variables requises** (cf. `check_env.py`) : `DATABASE_URL`, `RESEND_API_KEY`, `SENDER_EMAIL`, `STRIPE_SECRET_KEY`, `STRIPE_PUBLIC_KEY`, `STRIPE_WEBHOOK_SECRET`.
- **Replit** : définir aussi `SITE_URL` (URL publique), et éventuellement `CORS_ORIGINS` si le front est sur un autre domaine. Vérifier que le webhook Stripe pointe vers `https://<replit>/webhook/stripe` et que le secret est le bon (whsec_...).

---

## 5. Base de données

- En production, **DATABASE_URL** doit pointer vers PostgreSQL (ex. Supabase, pooler port 6543 si indiqué).
- La table **users** doit exister avec les colonnes décrites dans `SUPABASE_CREATE_TABLE.md` (dont `stripe_connect_*`). Sans ces colonnes, `get_stripe_connect_info` ne pourra pas renvoyer les infos Connect pour les coachs.
- `db_service` utilise un timeout de connexion (`DATABASE_CONNECT_TIMEOUT`, défaut 10 s) — adapté pour éviter des blocages longs.

---

## 6. Checklist avant mise en ligne Replit

- [ ] Variables d’environnement : DATABASE_URL, RESEND_API_KEY, SENDER_EMAIL, STRIPE_*, SITE_URL, CORS_ORIGINS si besoin.
- [ ] Table `users` créée (script SUPABASE_CREATE_TABLE.md) avec colonnes Stripe Connect.
- [ ] Webhook Stripe configuré : URL = `https://<ton-replit>/webhook/stripe`, secret copié dans STRIPE_WEBHOOK_SECRET.
- [x] **Appliqué** : `GET /api/coach/bookings` exige une session coach.
- [x] **Appliqué** : `GET /api/booking/{booking_id}` exige session + vérification client/coach de la réservation.
- [x] **Appliqué** : `POST/GET /api/messages/*`, `GET /api/conversations`, `mark-read` exigent session + vérification participant.
- [x] **Appliqué** : Rate limit 20/min sur cancel-booking, 8/min sur signup-reservation ; route `/images/` → 404.
- [ ] Tester un flux complet : inscription coach → profil → Stripe Connect → réservation client → paiement séance → webhook → emails.

---

## 7. Conclusion

Le projet est **prêt pour un premier déploiement** sur Replit avec les précautions suivantes :

- **Obligatoire** : env vars, table `users`, webhook Stripe.
- **Fortement recommandé** : protéger les APIs de réservations et de messages par authentification (session) pour éviter la fuite de données et l’usurpation.
- **Recommandé** : rate limits sur cancel-booking (et signup-reservation), correction de la route `/images/`, puis à moyen terme CSRF et renforcement de la validation (EmailStr, CSP).

Une fois les points « recommandés » ci-dessus traités, l’ensemble sera **carré** pour une mise en production avec de nombreux utilisateurs et coachs.

---

## 8. Correctifs additionnels (CSRF, EmailStr, CSP)

- **CSRF** : Token généré sur les GET login, signup, coach-login ; cookie `csrf_token` (HttpOnly, SameSite=Lax) ; vérification sur POST login, signup, coach-login et auth/resend-confirmation. Champs cachés `csrf_token` ajoutés dans les templates.
- **EmailStr** : Champs email des modèles Pydantic passés en `EmailStr` (SendOTPRequest, VerifyOTPRequest, SignupReservationRequest, ConfirmBookingRequest, CancelBookingRequest, CoachBookingRequest, SendMessageRequest).
- **CSP** : En-tête `Content-Security-Policy` ajouté dans le middleware (scripts/styles self + CDN, images self + data + https, frame-ancestors 'none').

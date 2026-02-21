# Checklist avant mise en ligne publique – FitMatch

À valider avant d’ouvrir le site à tous les utilisateurs (coachs et clients).

---

## 1. Variables d’environnement (hébergeur)

À configurer dans les paramètres du projet (Vercel, Netlify, etc.) :

| Variable | Obligatoire | Rôle |
|----------|-------------|------|
| **DATABASE_URL** | Oui | PostgreSQL (utilisateurs, réservations, abonnements). Sans elle l’app ne démarre pas. |
| **STRIPE_SECRET_KEY** | Oui | Paiements (abonnements coach + séances). |
| **STRIPE_WEBHOOK_SECRET** | Oui en prod | Vérification de la signature du webhook Stripe. Sans elle, risque de faux événements. |
| **STRIPE_PUBLIC_KEY** | Oui (front) | Clé publique Stripe pour le formulaire de paiement côté client. |
| **RESEND_API_KEY** | Oui | Envoi des emails (OTP, confirmations, rappels, blocage, etc.). |
| **SENDER_EMAIL** | Oui | Adresse d’envoi (ex. `contact@fitmatch.fr` ou `noreply@fitmatch.fr`). Doit être autorisée dans Resend. |
| **SUPABASE_URL** / **SUPABASE_ANON_KEY** | Si auth Supabase | Connexion / inscription avec Supabase. |
| **SUPABASE_JWT_SECRET** | Recommandé en prod | Vérification des tokens (sécurité). |
| **CORS_ORIGINS** | En prod | Origines autorisées, ex. `https://ton-domaine.com,https://www.ton-domaine.com`. |
| **SITE_URL** | Recommandé | URL publique du site (ex. `https://fitmatch.fr`). Utilisée dans les liens des emails et redirections Stripe. |
| **GOOGLE_MAPS_API_KEY** | Optionnel | Carte et recherche de salles. |

---

## 2. Stripe

- [ ] **Webhook** créé dans le tableau de bord Stripe (Developers → Webhooks → Add endpoint).
- [ ] **URL du webhook** = `https://ton-domaine.com/api/stripe/webhook` (exactement ton domaine).
- [ ] **Événements** au minimum :  
  `checkout.session.completed`, `invoice.payment_succeeded`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`, `account.updated` (pour Connect).
- [ ] **Signing secret** du webhook copié dans **STRIPE_WEBHOOK_SECRET** sur l’hébergeur.
- [ ] En **mode live** : clés live (pk_live_..., sk_live_...) et webhook en live.

---

## 3. Base de données (PostgreSQL)

- [ ] Base créée et **DATABASE_URL** correcte (user, mot de passe, host, port, nom de la base).
- [ ] Migrations appliquées si tu en as (voir `migrations/README.md`).
- [ ] Aucun mode démo : tout passe par la base (utilisateurs, réservations, statuts coach).

---

## 4. Emails (Resend)

- [ ] **RESEND_API_KEY** configurée.
- [ ] **SENDER_EMAIL** = adresse vérifiée dans Resend (domaine ou adresse perso selon ton plan).
- [ ] Vérifier que les emails partent bien pour :  
  - Inscription / OTP  
  - Confirmation de réservation client  
  - Reçu de paiement séance  
  - Notification coach (nouvelle résa)  
  - Rappels 24 h et 2 h avant la séance  
  - Refus / annulation  
  - Abonnement coach (succès, échec, blocage, restauration)

---

## 5. Parcours client

- [ ] **Inscription** : formulaire, OTP par email, création de compte.
- [ ] **Recherche** : par ville / code postal / salle, résultats cohérents.
- [ ] **Réservation** :  
  - Si coach sans paiement en ligne : demande envoyée, coach peut accepter/refuser, email de confirmation au client.  
  - Si coach avec paiement en ligne : redirection Stripe, paiement, puis confirmation + reçu par email.
- [ ] **Mon compte** (`/mon-compte`) : client connecté voit ses réservations (depuis la base via l’API).
- [ ] **Annulation** : client peut annuler, email au coach (et réciproque si besoin).
- [ ] **Rappels** : 24 h et 2 h avant la séance (si le job/rappels est exécuté côté serveur).

---

## 6. Parcours coach

- [ ] **Inscription coach** : formulaire, puis **paiement abonnement** (Stripe) obligatoire avant accès.
- [ ] **Profil** : photo, zone, spécialités, salles, tarifs, mode de paiement (désactivé / obligatoire).
- [ ] **Stripe Connect** (si paiement en ligne) :  
  - Lien d’onboarding Connect, compte lié, statut (charges_enabled, etc.) mis à jour (webhook `account.updated`).  
  - Les séances payées par le client sont bien transférées au coach.
- [ ] **Abonnement** :  
  - Page abonnement, renouvellement, accès au portail client Stripe (factures, moyen de paiement).  
  - Si paiement échoue : email d’avertissement, puis après 24 h blocage du compte + email.  
  - Si le coach paye à nouveau : déblocage + email de restauration.
- [ ] **Visibilité** : les coachs avec statut `blocked`, `cancelled` ou `past_due` sont **cachés** (recherche, page salle, profil public).
- [ ] **Réservations** : le coach reçoit l’email pour une nouvelle demande, peut accepter ou refuser ; en cas d’acceptation le client reçoit la confirmation (et le reçu si paiement en ligne).

---

## 7. Sécurité et technique

- [ ] **CORS** : en prod, **CORS_ORIGINS** = tes vrais domaines (pas `*` si possible).
- [ ] **JWT** : **SUPABASE_JWT_SECRET** (ou **JWT_SECRET_KEY**) défini pour vérifier les tokens en prod.
- [ ] **HTTPS** : le site et l’API sont servis en HTTPS.
- [ ] **404 / 500** : les pages d’erreur s’affichent correctement (pas de JSON brut pour les utilisateurs).
- [ ] **SITE_URL** : défini avec l’URL publique du site pour les liens dans les emails et les redirections Stripe (ex. paiement séance client).

---

## 8. Contenu et légal (recommandé)

- [ ] **Mentions légales** / CGU / politique de confidentialité si ton hébergeur ou la loi l’exige.
- [ ] **Contact** : une adresse ou un formulaire pour les utilisateurs (ex. lien “Contact” dans le footer ou les emails).

---

## Résumé

- **Obligatoire** : DATABASE_URL, Stripe (clés + webhook + secret), Resend (API key + expéditeur), CORS et JWT en prod, SITE_URL pour les liens.
- **Parcours** : inscription → recherche → réservation (avec ou sans paiement) → confirmation / reçu par email → mon compte → rappels et annulations.
- **Coach** : abonnement payant, Connect pour recevoir les paiements, blocage après 24 h sans régularisation, profils bloqués invisibles.

Quand tout est coché, tu peux lancer le site publiquement pour les coachs et les clients.

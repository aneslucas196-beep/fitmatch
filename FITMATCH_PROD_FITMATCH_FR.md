# Configuration fitmatch.fr – Paiement Stripe Coach

## Problème : la page de paiement Stripe n’apparaît pas

**Causes possibles :**

1. **`SITE_URL` non défini** → redirections vers une mauvaise URL (ex. http au lieu de https, ou domaine interne).
2. **Clés Stripe manquantes ou invalides** → le bouton « Payer » renvoie une erreur.
3. **Cookie de session perdu** → l’API `/api/stripe/create-checkout-session` renvoie 401.

---

## À configurer sur fitmatch.fr

### Variables d’environnement obligatoires

```bash
# OBLIGATOIRE – URL publique du site
SITE_URL=https://fitmatch.fr

# Stripe (abonnement coach 30€/mois)
STRIPE_PUBLIC_KEY=pk_live_xxx   # ou pk_test_xxx en test
STRIPE_SECRET_KEY=sk_live_xxx   # ou sk_test_xxx en test
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Autres (déjà documentés dans .env.example)
DATABASE_URL=postgresql://...
RESEND_API_KEY=re_xxx
SENDER_EMAIL=noreply@fitmatch.fr
```

### À vérifier côté Stripe

1. **Dashboard Stripe** → Webhooks → ajouter  
   `https://fitmatch.fr/webhook/stripe`  
   et configurer les événements : `checkout.session.completed`, `customer.subscription.*`, `invoice.*`.
2. Copier le **signing secret** (whsec_...) dans `STRIPE_WEBHOOK_SECRET`.

### Si le site est derrière un proxy (Render, Replit, etc.)

Les headers `X-Forwarded-Proto` et `X-Forwarded-Host` doivent être transmis :

- Render : automatique.
- Replit : automatique.
- Nginx : `proxy_set_header X-Forwarded-Proto $scheme;` et `proxy_set_header Host $host;`.

---

## Flux coach après correction

1. Inscription coach sur `/coach-login` (onglet Inscription).
2. Redirection vers `https://fitmatch.fr/coach/pay?token=xxx`.
3. Page « Payer 30€ par carte » affichée.
4. Clic sur « Payer » → appel API → redirection vers Stripe Checkout.
5. Paiement sur Stripe → retour sur `https://fitmatch.fr/coach/subscription?success=true&session_id=...`.
6. Abonnement activé → envoi OTP email → redirection vers vérification email.

---

## Test rapide

1. S’inscrire en tant que coach avec un email de test.
2. Vérifier que la redirection pointe bien vers `https://fitmatch.fr/coach/pay`.
3. Cliquer sur « Payer par carte bancaire » : la page Stripe Checkout doit s’ouvrir.
4. Annuler le paiement : retour sur `https://fitmatch.fr/coach/subscription?cancelled=true`.

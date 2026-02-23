# Checklist Stripe – pour que la page de paiement s’affiche

Si après inscription coach tu n’arrives pas sur la page Stripe pour payer, vérifie les points suivants.

---

## 1. Sur Render (variables d’environnement)

- **SITE_URL** = `https://fitmatch.fr` (sans espace avant/après)
- **STRIPE_PUBLIC_KEY** = ta clé `pk_live_...`
- **STRIPE_SECRET_KEY** = ta clé `sk_live_...`
- **STRIPE_WEBHOOK_SECRET** = ton secret `whsec_...` (pour les webhooks)

Après toute modification des variables, fais un **Manual Deploy** pour que les changements soient pris en compte.

---

## 2. Dans le tableau de bord Stripe (stripe.com)

### Mode Live
- En haut à droite, tu dois être en **mode Live** (et non Test).
- Les clés doivent être **Live** : `pk_live_...` et `sk_live_...`.

### Compte activé
- **Paramètres** → **Compte** : le compte doit être **activé** (informations business, compte bancaire pour les paiements).
- Si le compte n’est pas encore activé, Stripe peut refuser de créer une session de paiement.

### Produits / Prix
- Avec le code actuel, on utilise des **prix dynamiques** (pas de produit créé à l’avance). Aucune création de produit n’est obligatoire dans le dashboard pour que Checkout fonctionne.

---

## 3. Ce qui a été corrigé dans le code

- **URLs de retour Stripe** : elles sont maintenant construites avec **SITE_URL** (`https://fitmatch.fr`) au lieu de l’URL interne du serveur. Sinon Stripe pouvait recevoir des URLs invalides et refuser ou mal rediriger.
- **Cookie sur les appels API** : les boutons « S’abonner » envoient bien le cookie de session (`credentials: 'include'`) pour que le serveur reconnaisse le coach.
- Si l’API Stripe renvoie une erreur, le **message d’erreur** s’affiche dans une alerte pour que tu voies exactement ce que Stripe renvoie.

---

## 4. Tester

1. Va sur https://fitmatch.fr/coach-login?tab=signup
2. Inscris-toi avec un **nouvel email** (jamais utilisé).
3. Tu dois arriver sur la page **Abonnement** (30€/mois, 300€/an).
4. Clique sur **« S’abonner maintenant »** (30€/mois).
5. Si tout est bon → tu es redirigé vers la **page Stripe** (saisie carte).
6. Si une **alerte** s’affiche avec un message d’erreur, note ce message (il vient du serveur ou de Stripe) et vérifie la checklist ci-dessus.

---

## 5. Erreurs fréquentes

| Message / Comportement | Cause probable | Action |
|------------------------|----------------|--------|
| « Paiement temporairement indisponible » | Clés Stripe non prises en compte ou mal configurées | Vérifier STRIPE_PUBLIC_KEY et STRIPE_SECRET_KEY sur Render, puis redéployer. |
| « Authentification requise » ou redirection vers /login | Cookie de session non envoyé ou perdu | Vérifier SITE_URL sur Render. Tester en navigation privée avec un nouvel email. |
| Message d’erreur Stripe (ex. « Your account cannot currently make live charges ») | Compte Stripe pas encore activé pour le mode Live | Compléter l’activation du compte dans Stripe (Paramètres → Compte). |
| Aucune alerte, rien ne se passe au clic | Erreur réseau ou CORS | Ouvrir la console du navigateur (F12 → Console) et regarder les erreurs en rouge. |

En cas de message d’erreur précis (alerte ou console), tu peux le copier et l’utiliser pour cibler le problème (côté Stripe ou côté app).

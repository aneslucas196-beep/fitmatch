# Après que tu m’envoies les clés Stripe + Google Maps

## Ce que tu m’envoies

1. **Stripe** (depuis [dashboard.stripe.com](https://dashboard.stripe.com) → Developers → API keys)  
   - `STRIPE_PUBLIC_KEY` (commence par `pk_test_` ou `pk_live_`)  
   - `STRIPE_SECRET_KEY` (commence par `sk_test_` ou `sk_live_`)  

2. **Google Maps** (depuis [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials)  
   - `GOOGLE_MAPS_API_KEY` (ou `GOOGLE_PLACES_API_KEY`)  

Tu peux les coller ici (en privé) ou les mettre toi-même dans le fichier **`.env`** et me dire « c’est fait ».

---

## Ce que je fais dès que j’ai les clés

1. **Je mets tout dans ton `.env`**  
   - Stripe (public + secret)  
   - Google Maps  
   - Rien d’autre à configurer côté clés.

2. **Je te dis ce qu’il reste**  
   - Côté code/config : **rien**. Tout sera prêt.  
   - Il restera uniquement : **mettre le site en ligne** pour qu’il tourne 24h/24.

3. **Je te rappelle les étapes pour que le serveur tourne 24/7**  
   - Le serveur ne peut pas tourner 24/7 sur ton PC (il s’arrête quand tu éteinds ou fermes le terminal).  
   - Pour du **vrai 24/7**, il faut l’héberger chez un hébergeur (ex. **Render**).  
   - Je ne peux pas créer ton compte Render ni cliquer à ta place.  
   - Ce que je fais : **je te donne le guide exact** (déjà dans **DEPLOY_RENDER_5_STEPS.md**) pour que, en quelques clics, tu déploies le site sur Render. Une fois déployé, **Render** fait tourner le serveur 24/7 pour toi.

---

## Ce qu’il restera à faire (pour toi, une seule fois)

1. Aller sur **[render.com](https://render.com)** et créer un compte (ex. avec GitHub).  
2. Suivre **DEPLOY_RENDER_5_STEPS.md** :  
   - Créer une base PostgreSQL (sur Render).  
   - Créer un **Web Service** relié à ton repo FitMatch.  
   - Coller dans Render **toutes** les variables de ton `.env` (Build command + Start command sont déjà indiqués dans le guide).  
   - Cliquer sur Deploy.  
3. (Optionnel) Créer le **Background Worker** pour les rappels 24h/2h (décrit dans le même guide).  

Après ça, **plus rien à lancer** : le site et le worker tournent 24/7 sur les serveurs de Render.

---

## Récap

| Étape | Qui | Quoi |
|-------|-----|------|
| Tu m’envoies | Stripe (pk_ + sk_) + Google Maps | En chat ou dans `.env` |
| Je fais | Mise à jour de `.env`, vérif que tout est prêt | Plus rien à coder |
| Il reste | Toi, une fois | Déployer sur Render (guide en 5 étapes) |
| Résultat | Render | Serveur + rappels 24/7 |

Dès que tu m’envoies les clés Stripe et Google Maps, je m’occupe du `.env` et je te redis ce qu’il reste (en pratique : juste le déploiement Render).

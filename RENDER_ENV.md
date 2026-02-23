# Configuration Render pour fitmatch.fr

Tes variables sont déjà bien remplies. Il reste **une seule chose à corriger** pour que la base de données fonctionne sur Render.

---

## ⚠️ Important : ne jamais coller tes vrais secrets (clés API, mots de passe) dans un chat ou un fichier partagé

Si tu l’as fait, **régénère** les clés concernées dans chaque dashboard (Stripe, Supabase, Resend) et mets à jour les variables sur Render. Les anciennes ne doivent plus être utilisées.

---

## 1. DATABASE_URL : utiliser le pooler Supabase (obligatoire sur Render)

Sur Render, la connexion **directe** à Supabase (port **5432**) est souvent bloquée ou inaccessible (« Network is unreachable »). Il faut utiliser l’URL du **pooler** (port **6543**).

### Étapes

1. Ouvre **Supabase** → ton projet → **Project Settings** (icône engrenage) → **Database**.
2. Dans **Connection string**, choisis l’onglet **Connection pooling**.
3. Choisis **Session mode** (ou Transaction mode).
4. Copie l’URL. Elle ressemble à :
   ```text
   postgresql://postgres.[TON_PROJECT_REF]:[MOT_DE_PASSE]@aws-0-[REGION].pooler.supabase.com:6543/postgres
   ```
   (avec **6543**, pas 5432, et le host se termine par **pooler.supabase.com**).
5. Remplace `[YOUR-PASSWORD]` par le vrai mot de passe de la base (le même que pour l’URL directe).
6. Sur **Render** → ton Web Service → **Environment** → modifie **DATABASE_URL** et colle cette nouvelle URL (pooler, port 6543).

Après redéploiement, l’erreur « connection to server at ... port 5432 failed: Network is unreachable » doit disparaître et la base sera utilisée.

---

## 2. Variables déjà correctes (à ne pas casser)

Tu as déjà tout le reste. Garde tel quel sur Render :

| Variable | Rôle |
|----------|------|
| **CORS_ORIGINS** | `https://fitmatch.fr,https://www.fitmatch.fr` – CORS pour ton domaine. |
| **SITE_URL** | `https://fitmatch.fr` – Cookies de session (connexion après inscription coach). |
| **GOOGLE_MAPS_API_KEY** / **GOOGLE_PLACES_API_KEY** | Recherche de salles et cartes. |
| **STRIPE_PUBLIC_KEY** / **STRIPE_SECRET_KEY** / **STRIPE_WEBHOOK_SECRET** | Paiements et abonnements coach. |
| **SUPABASE_URL** / **SUPABASE_KEY** / **SUPABASE_JWT_SECRET** | Auth et JWT. |
| **RESEND_API_KEY** / **SENDER_EMAIL** | Envoi d’emails. |
| **PYTHON_VERSION** | `3.12.8` – OK. |

Aucune modification nécessaire pour celles-ci.

---

## 3. Résumé

- **À faire** : remplacer **DATABASE_URL** sur Render par l’URL du **pooler Supabase** (port **6543**, host **pooler.supabase.com**), comme expliqué au §1.
- **Sécurité** : ne plus partager tes clés ; si déjà fait, les régénérer et mettre à jour Render.
- Le reste de ta config Render est bon.

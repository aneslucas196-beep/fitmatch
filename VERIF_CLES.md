# Vérification des clés et du site

## Clés que tu as envoyées — statut

| Clé | Statut | Remarque |
|-----|--------|----------|
| **SUPABASE_URL** | OK | Format correct, projet Supabase cohérent |
| **SUPABASE_KEY** (anon) | OK | JWT valide |
| **SUPABASE_JWT_SECRET** | OK | Présent |
| **DATABASE_URL** | OK | Même projet que Supabase (db.vfcrabxqwloauxrbyxyo.supabase.co) |
| **RESEND_API_KEY** | OK | Format `re_...` |
| **SENDER_EMAIL** | OK | contact@fitmatch.fr |
| **STRIPE_WEBHOOK_SECRET** | OK | Format `whsec_...` |
| **CORS_ORIGINS** / **SITE_URL** | OK | fitmatch.fr |

Aucune faute détectée sur ces clés (formats et cohérence vérifiés).

---

## Ce qui manque (à m’envoyer ou à mettre dans `.env`)

1. **Stripe (paiements)**  
   - `STRIPE_PUBLIC_KEY` (pk_test_... ou pk_live_...)  
   - `STRIPE_SECRET_KEY` (sk_test_... ou sk_live_...)  
   → Remplacer les placeholders `pk_test_xxx` et `sk_test_xxx` dans `.env`.

2. **Google Maps**  
   - `GOOGLE_MAPS_API_KEY`  
   → Ligne ajoutée dans `.env` (vide pour l’instant). Dès que tu as la clé, mets-la dans `.env` ou envoie-la-moi.

Sans Stripe : le site peut démarrer mais les paiements ne marcheront pas.  
Sans Google Maps : le site marche ; seule la carte / recherche d’adresses peut être limitée ou désactivée.

---

## Résumé

- **Clés déjà envoyées :** vérifiées, pas de faute. Tout est bien enregistré dans `.env`.
- **À envoyer / à remplir :** uniquement les **clés Stripe** (pk_ + sk_) et la **clé Google Maps** quand tu l’as.

Après avoir ajouté Stripe + Google Maps, il ne restera plus qu’à déployer (ex. Render) pour que le serveur tourne 24/7.

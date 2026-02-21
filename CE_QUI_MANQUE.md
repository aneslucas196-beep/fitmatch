# Ce qui manque (ou à vérifier) avant mise en ligne

Vérification faite sur tout le site. Liste de ce qui reste à faire ou à décider.

---

## 1. Pages légales / contact — FAIT

**Fait :** Les 3 pages existent et les liens sont à jour.
- **`/mentions-legales`** : mentions légales / CGU
- **`/confidentialite`** : politique de confidentialité
- **`/contact`** : page contact (email contact@fitmatch.fr)

Le footer (`index.html`) et la page réservation (`reservation.html`) pointent vers ces URLs. Tu peux adapter le contenu des templates si besoin (mentions_legales.html, confidentialite.html, contact.html).

---

## 2. Rappels 24 h / 2 h en production (serverless)

**Comment ça marche aujourd’hui :**
- Les rappels sont enregistrés dans `scheduled_reminders.json`.
- Un **thread** dans l’app appelle `process_due_reminders()` toutes les 5 minutes.

**En serverless (ex. Vercel) :** Le thread ne tourne pas et le fichier JSON n’est en général pas persistant entre les invocations.

**À faire si tu es en serverless :**
- Configurer un **cron** (Vercel Cron, cron-job.org, etc.) qui appelle **GET `/api/reminders/process`** toutes les 5 à 15 minutes (avec une clé secrète en header ou en query si tu sécurises la route).
- Ou migrer le stockage des rappels en base de données (PostgreSQL) pour qu’ils survivent et soient traités par ce cron.

Sinon, les rappels 24 h et 2 h avant la séance ne partiront pas en prod.

---

## 3. Expéditeur des emails (SENDER_EMAIL)

**Modif faite :** Le code utilise maintenant **SENDER_EMAIL** (variable d’environnement) pour l’expéditeur de tous les emails Resend. Si elle n’est pas définie, on utilise `contact@fitmatch.fr`.

**À faire :** Définir **SENDER_EMAIL** sur l’hébergeur (ex. `contact@fitmatch.fr` ou `noreply@fitmatch.fr`) et vérifier que ce domaine/adresse est autorisé dans Resend.

---

## 4. Favicon et meta description — FAIT (favicon à ajouter)

- **Meta description :** Ajoutée dans `base.html` et `index.html` (contenu par défaut + traduction si dispo).
- **Favicon :** Le lien `<link rel="icon" href="/static/favicon.ico">` est en place. Il te reste à **déposer un fichier `favicon.ico`** dans le dossier **`static/`** pour qu’il s’affiche.

---

## 5. Sécurisation de `/api/reminders/process` — FAIT

**Fait :** Si la variable **CRON_SECRET** est définie en env, l’endpoint exige ce secret en query (`?secret=...`) ou en header **X-Cron-Secret**. Sinon (dev), l’appel reste possible sans secret.

**À faire en prod :** Définir **CRON_SECRET** sur l’hébergeur et configurer ton cron pour envoyer ce secret à chaque appel.

---

## Récap : déjà en place

- Variables d’env (DATABASE_URL, Stripe, Resend, CORS, JWT, SITE_URL) branchées.
- Parcours client et coach (inscription, résa, paiement, abonnement, Connect, blocage).
- Emails (OTP, confirmation, reçu, rappels, blocage, etc.) avec Resend.
- 404 / 500 en HTML, i18n, CORS, vérification JWT.
- Utilisation de **SENDER_EMAIL** pour l’expéditeur des emails.

---

## En résumé

| Priorité | Élément | Statut |
|----------|--------|--------|
| Haute | CGU / Confidentialité / Contact | Fait : pages et liens en place. |
| Haute | Rappels en serverless | À faire : cron vers `/api/reminders/process` (avec CRON_SECRET si défini). |
| Moyenne | SENDER_EMAIL | Définir sur l’hébergeur et vérifier le domaine dans Resend. |
| Basse | Favicon | Lien en place ; ajouter le fichier `static/favicon.ico`. |
| Basse | Sécuriser `/api/reminders/process` | Fait : CRON_SECRET optionnel (query ou header X-Cron-Secret). |

Une fois les points « haute priorité » traités, le site est prêt pour une mise en ligne publique côté fonctionnel et légal.

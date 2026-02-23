# Vérification complète du site (hors Stripe)

## 1. Rappels 24h et 2h avant le RDV

### Logique
- **Programmation** : à chaque réservation **confirmée**, `schedule_booking_reminders(booking, coach_name)` est appelé.
- **Rappel 24h** : envoyé à `booking_datetime - 24h` (si le RDV est dans plus de 24h).
- **Rappel 2h** : envoyé à `booking_datetime - 2h` (si le RDV est dans plus de 2h).
- **Annulation** : quand une réservation est annulée, `cancel_booking_reminders(booking_id)` retire tous les rappels liés.

### Envoi
- **Boucle** : au démarrage de l’app, un thread daemon lance `_reminders_loop()` qui appelle `process_due_reminders()` puis `time.sleep(REMINDERS_LOOP_INTERVAL)` (défaut 60 s).
- **Traitement** : `process_due_reminders()` charge les rappels, pour chaque rappel non envoyé avec `send_at <= now` appelle `send_reminder_email(...)`, marque `sent` et sauvegarde. Puis `cleanup_old_reminders()` supprime les rappels envoyés depuis plus de 7 jours.

### Emails de rappel
- **Resend** : `send_reminder_email(..., reminder_type="24h"|"2h", lang=...)` envoie l’email via l’API Resend.
- **Traductions** : dans chaque `translations/{lang}.json`, la section **emails** contient `reminder_subject_24h`, `reminder_subject_2h`, `reminder_body_24h`, `reminder_body_2h` (fr, en, es, de, it, ar, pt).

### Modifs effectuées
- **Heure** : normalisation de l’heure de réservation pour accepter "14:00" et "14:00:00" avant le `strptime`.
- **Robustesse** : parsing de `send_at` en `try/except` et gestion des chaînes vides ou invalides pour ne pas faire planter la boucle.

---

## 2. Emails (Resend)

### Types d’emails utilisés
- OTP (code vérification)
- Confirmation de réservation
- **Rappels 24h et 2h**
- Annulation (client + coach)
- Notification coach (nouvelle demande)
- Refus de demande
- Reçu paiement séance / abonnement
- Échec paiement / compte bloqué / restauré
- Inscription coach (échec paiement)

### Configuration
- **Expéditeur** : `SENDER_EMAIL` (défaut `contact@fitmatch.fr`) via `_mail_from()`.
- **Clé** : `RESEND_API_KEY`. Si absente, les fonctions retournent `{"success": False, "error": "..."}` sans faire planter l’app.

### Traductions des emails
- Chargement via `get_email_translations(lang)` qui lit `translations/{lang}.json` → clé **emails**.
- Toutes les langues (fr, en, es, de, it, ar, pt) ont une section **emails** avec les clés nécessaires (dont rappels 24h/2h, hello, coach_label, date_label, at, etc.).

---

## 3. Traductions (i18n)

### Langues
- **Supportées** : fr, en, es, ar, de, it, pt (`SUPPORTED_LOCALES` dans `i18n_service.py`).
- **Fichiers** : `translations/fr.json`, `en.json`, `es.json`, `ar.json`, `de.json`, `it.json`, `pt.json`.

### Utilisation
- **Pages** : `get_locale_from_request(request)` (query `lang`, cookie, chemin, Accept-Language).
- **Préchargement** : `preload_all_translations()` au démarrage.
- **Templates** : passage de `t` (traductions) et `locale` ; usage du type `t.nav.home`, `t.legal.contact_title` avec `|default('...')` pour éviter les clés manquantes.

### Sections vérifiées
- **nav**, **home**, **footer**, **legal** (contact, CGU, confidentialité), **subscription** (abonnement coach).
- **emails** (dans chaque JSON) : rappels 24h/2h, OTP, confirmation, annulation, etc.

---

## 4. Pages et liens

- **Mentions légales** : `/mentions-legales` → `mentions_legales.html` (avec fallbacks si `t.legal` manquant).
- **Confidentialité** : `/confidentialite` → `confidentialite.html`.
- **Contact** : `/contact` → `contact.html` (email contact@fitmatch.fr).
- Liens entre ces pages et vers l’accueil cohérents.

---

## 5. Récapitulatif

| Élément | Statut |
|--------|--------|
| Rappels 24h avant | OK (programmation, envoi, email Resend, traductions) |
| Rappels 2h avant | OK (idem) |
| Emails (tous types) | OK (Resend, SENDER_EMAIL, traductions emails) |
| Traductions (7 langues) | OK (structure, emails, legal, nav, fallbacks) |
| Pages légales / contact | OK (templates + fallbacks) |
| Robustesse rappels | OK (heure normalisée, send_at parsé sans crash) |

Tout a été vérifié ; les seules modifications apportées sont la normalisation de l’heure des rappels et le parsing sécurisé de `send_at`. Le reste du site (hors Stripe) est cohérent.

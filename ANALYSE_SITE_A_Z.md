# Analyse du site FitMatch – A à Z

## 1. Traductions (i18n)

### Langues supportées
- **Fichiers** : `translations/fr.json`, `en.json`, `es.json`, `de.json`, `it.json`, `pt.json`, `ar.json`
- **Service** : `i18n_service.py` – `SUPPORTED_LOCALES = ['fr', 'en', 'es', 'ar', 'de', 'it', 'pt']`
- **Détection** : priorité `?lang=` > cookie `fitmatch_locale` > préfixe URL > en-tête `Accept-Language` > défaut

### Pages avec i18n correct
- Accueil, recherche, résultats, login, signup, coach_login, coach_subscription, coach_portal
- Réservation, contact, mentions légales, confidentialité, conversation
- client_home, partner, error, 404

### Corrections effectuées
- **booking.html** : `lang="fr"` → `lang="{{ locale|default('fr') }}"` + `dir="rtl"` si arabe
- **account.html** : idem
- **coach_profile.html** : idem
- **booking.html** : ajout du paramètre `lang` dans l’URL vers `/reservation` (récupération depuis le cookie) pour que la page réservation et les e-mails utilisent la bonne langue

---

## 2. E-mails selon la langue de l’utilisateur

### Règle
- **Client** : langue de la **réservation** = langue du site au moment de la réservation (cookie `fitmatch_locale`), stockée dans le champ `lang` de la réservation.
- **Coach** : langue du **profil coach** (`coach_data.get("lang", "fr")`) pour les e-mails envoyés au coach.

### E-mails concernés et utilisation de `lang`

| E-mail | Destinataire | Source de `lang` |
|--------|--------------|-------------------|
| OTP (vérification) | Client/Coach | `locale` de la requête (page signup/login) |
| Confirmation réservation | Client | `booking.get("lang", "fr")` |
| Notification nouvelle demande | Coach | `coach_data.get("lang", "fr")` |
| Rappel 24h/2h | Client | `reminder.get("lang", "fr")` (stocké à la création du rappel) |
| Annulation (client) | Client | `request.lang` (annulation) ou `booking.lang` |
| Annulation (coach) | Coach | `coach_data.get("lang", "fr")` |
| Coach a annulé | Client | `deleted_booking.get("lang", "fr")` |
| Compte bloqué / paiement échoué | Coach | `user_data.get("lang", "fr")` |
| Abonnement réussi / reçu abonnement | Coach | `coach_data.get("lang", "fr")` |
| Reçu paiement séance | Client | `booking.get("lang", "fr")` |
| Paiement séance échoué | Client | métadonnées Stripe ou défaut |

### Flux réservation et langue
- Page **réservation** : `reservation.js` envoie déjà `lang` (cookie `fitmatch_locale`) dans le body vers `/api/confirm-booking`.
- Le backend enregistre `request.lang` dans `new_booking["lang"]`.
- Les rappels sont créés avec la même langue (stockée dans la réservation).
- **booking.html** : la redirection vers `/reservation` inclut maintenant `lang=...` dans l’URL pour cohérence.

### Corrections effectuées
- Appels à `send_booking_confirmation_email` : `booking_id=...` remplacé par `reservation_id=...` (et ajout de `coach_photo` où il manquait) pour correspondre à la signature du service.

---

## 3. Fichiers de traduction des e-mails

- Section **emails** dans chaque `translations/{lang}.json` (fr, en, es, de, it, pt, ar).
- Clés utilisées : sujet/corps pour OTP, confirmation, rappels, annulation, annulation par le coach, notification coach, reçus, échec paiement, compte bloqué, etc.
- `resend_service.get_email_translations(lang)` charge la section `emails` du fichier correspondant.

---

## 4. Pages et templates

- **Index, recherche, résultats** : i18n OK.
- **Login, signup, verify_otp, coach_login, coach_signup** : i18n OK.
- **Réservation** : locale + `t` passés ; `reservation.js` envoie `lang` au backend.
- **Compte** : `/account`, `/account/info`, `/account/payments` avec onglets ; locale passée.
- **Coach** : portal, subscription, pay, profile_setup avec i18n.
- **Légal** : mentions légales, confidentialité, contact avec `?lang=` et cookie.

---

## 5. Améliorations possibles (recommandations)

1. **Photos** : vérifier les images par défaut (avatar, bannières) et remplacer par des visuels homogènes si besoin.
2. **Coordonnées coach** : s’assurer que le champ `lang` est bien enregistré en base (profil coach) pour les e-mails coach (abonnement, blocage, etc.).
3. **Rappels** : à la création des rappels (après confirmation), le `lang` est déjà pris depuis la réservation ; vérifier que chaque chemin qui crée un rappel remplit bien `reminder["lang"]`.
4. **DEFAULT_LOCALE** : dans `i18n_service.py` la valeur est `'en'` (fallback si fichier manquant). On peut la passer à `'fr'` si le site est prioritairement français.
5. **Tests** : ajouter des tests E2E ou manuels : réserver en EN puis en FR et contrôler la langue des e-mails reçus.

---

## 6. Résumé des corrections effectuées dans le code

- **main.py** : deux appels à `send_booking_confirmation_email` corrigés (`booking_id` → `reservation_id`, ajout `coach_photo`).
- **templates/booking.html** : `html lang` dynamique, `dir="rtl"` pour l’arabe, ajout de `lang` dans l’URL de redirection vers `/reservation`.
- **templates/account.html** : `html lang` dynamique, `dir="rtl"` pour l’arabe.
- **templates/coach_profile.html** : `html lang` dynamique, `dir="rtl"` pour l’arabe.

Avec ces changements, un utilisateur qui utilise le site en anglais (cookie ou `?lang=en`) reçoit les e-mails en anglais ; en français, en français. La langue est propagée de la page → formulaire de réservation → réservation → rappels et e-mails.

---

## Dernière passe : traductions A à Z (templates)

- **account** : section `account` ajoutée dans fr, en, es, de, it, pt, ar (titre, onglets, logout, messages info/paiements, modale annulation, statuts, boutons). `account.html` utilise `t.account.*` et `window.__ACCOUNT_I18N__` pour le JS (cartes de réservation, bonjour).
- **booking_page** : section `booking_page` ajoutée (titre, choix de créneau, légendes Dispo/Occupé/Passé, boutons, toast). `booking.html` utilise `t.booking_page.*` et `window.__BOOKING_PAGE_I18N__` pour les textes dynamiques en JS.
- **coach_pay** : section `coach_pay` ajoutée ; `coach_pay.html` reçoit i18n et utilise `t.coach_pay.*` + `__COACH_PAY_I18N__` pour le bouton et les messages d’erreur.
- **reservation_cancelled** : section ajoutée (fr, en) ; `reservation_cancelled.html` utilise `t.reservation_cancelled.*` et `lang="{{ locale }}"`.
- **Formatage des dates** : sur la page compte, les dates sont formatées avec la locale de la page (`window.__PAGE_LOCALE__` → `toLocaleDateString`).

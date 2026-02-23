# Activer toutes les salles du monde (Google Places) sur fitmatch.fr

Comme sur Replit : la recherche sur la page d'accueil utilise **Google Places API (New)** pour trouver **toutes les salles** (gyms, fitness, salles de sport) **dans le monde**.

---

## Guide pas à pas

### Partie A – Google Cloud (créer la clé et autoriser ton site)

1. **Ouvre Google Cloud Console**  
   → [https://console.cloud.google.com](https://console.cloud.google.com)  
   Connecte-toi avec ton compte Google.

2. **Choisis un projet (ou crée-en un)**  
   En haut à gauche : menu **Sélectionner un projet** → choisis le projet de ton app (ex. FitMatch) ou **Nouveau projet** (nomme-le puis valide).

3. **Activer l’API Places (New)**  
   - Menu **☰** → **APIs et services** → **Bibliothèque** (ou [Library](https://console.cloud.google.com/apis/library)).  
   - Dans la recherche, tape : **Places API (New)**.  
   - Clique sur **Places API (New)** → bouton **ACTIVER**.  
   - Si tu utilises aussi une carte ou l’ancienne API : active **Maps JavaScript API** ou **Places API** (ancienne) si besoin.

4. **Créer ou réutiliser une clé API**  
   - Menu **☰** → **APIs et services** → **Identifiants** (ou [Credentials](https://console.cloud.google.com/apis/credentials)).  
   - **Créer une clé** : clique sur **+ CRÉER DES IDENTIFIANTS** → **Clé API**.  
   - Une clé (ex. `AIzaSy...`) s’affiche. Tu peux la **copier** tout de suite ou la retrouver dans la liste des clés.  
   - Si tu as déjà une clé pour Maps/Places, tu peux utiliser celle-là (passe à l’étape 5).

5. **Restreindre la clé (recommandé) – referrers HTTP**  
   - Dans **Identifiants**, clique sur le **nom** de ta clé API (pas sur l’icône copier).  
   - Section **Restrictions relatives aux applications** :  
     - Choisis **Référents HTTP (sites web)**.  
     - Dans **Sites web autorisés**, clique **+ AJOUTER UN ÉLÉMENT** et ajoute **un par un** :
       - `https://fitmatch.fr/*`
       - `https://www.fitmatch.fr/*`
       - `https://fitmatch-fr.onrender.com/*`  
     - (Tu peux en ajouter d’autres plus tard, ex. `http://localhost:*` pour tester en local.)  
   - Section **Restrictions relatives aux API** :  
     - Choisis **Restreindre la clé**.  
     - Coche au minimum : **Places API (New)**.  
     - Sauvegarde la liste si tu utilises d’autres APIs (Maps, etc.).  
   - Clique sur **ENREGISTRER** en bas de la page.

6. **Copier la clé**  
   Tu dois avoir la clé en main (ex. `AIzaSy...`) pour la mettre sur Render à l’étape B.

---

### Partie B – Render (variable d’environnement)

1. **Ouvre le dashboard Render**  
   → [https://dashboard.render.com](https://dashboard.render.com)  
   Connecte-toi.

2. **Ouvre ton service (Web Service)**  
   Clique sur le service qui héberge FitMatch (ex. **fitmatch-fr** ou le nom de ton Web Service).

3. **Onglet Environment**  
   Dans le menu de gauche du service, clique sur **Environment**.

4. **Ajouter la variable**  
   - Clique sur **Add Environment Variable** (ou **Add Variable**).  
   - **Key** :  
     `GOOGLE_PLACES_API_KEY`  
     (ou `GOOGLE_MAPS_API_KEY` si ton code utilise ce nom – les deux sont supportés.)  
   - **Value** : colle ta clé API Google (ex. `AIzaSy...`).  
   - Ne coche pas **Secret** si tu préfères la voir en clair (la clé est déjà limitée par les referrers). Tu peux la mettre en **Secret** pour qu’elle soit masquée dans l’interface.  
   - Valide (Save / Add).

5. **Redéployer**  
   Pour que la variable soit prise en compte : **Manual Deploy** → **Deploy latest commit** (ou pousse un commit si le déploiement est automatique).  
   Attends la fin du déploiement.

6. **Tester**  
   Sur [https://fitmatch.fr](https://fitmatch.fr) (ou ton URL Render), va sur la page d’accueil et tape dans la recherche (ex. « Basic-Fit Paris » ou « Gold's Gym »).  
   Les salles devraient s’afficher après 2 caractères. Si rien n’apparaît, attends 1–2 minutes (propagation des restrictions de clé) et réessaie.

---

## Variables d'environnement (résumé)

- **Sur Render** : définir **`GOOGLE_PLACES_API_KEY`** (ou **`GOOGLE_MAPS_API_KEY`**) avec la clé API Google.
- Cette clé doit avoir **Places API (New)** activée et les **referrers HTTP** de ton domaine autorisés (voir Partie A).

## À faire dans Google Cloud Console (résumé)

1. [Console](https://console.cloud.google.com) → ton projet.
2. **APIs & Services** → **Library** → activer **Places API (New)**.
3. **APIs & Services** → **Credentials** → créer ou modifier une clé API.
4. **Restrictions** : **HTTP referrers** + ajouter `https://fitmatch.fr/*`, `https://www.fitmatch.fr/*`, `https://fitmatch-fr.onrender.com/*`.
5. **Save** puis mettre la clé dans Render (Partie B).

Quelques minutes après, la recherche mondiale (champ « Rechercher par ville ou code postal ») sur fitmatch.fr utilisera la même API et affichera les salles du monde entier.

## Comportement (style Replit)

- **Recherche** : au moins 2 caractères → appel à `places:searchText` avec type `gym`, puis élargissement sans type si peu de résultats.
- **Résultats** : salles avec nom, adresse, coordonnées (IDs `google_worldwide_...`).
- **Page salle** : `/gym/{id}` affiche les coachs qui ont ajouté cette salle à leur profil.

## Si la clé est en « None » (aucune restriction)

Le blocage ne vient pas du domaine. Vérifie dans les **Logs** Render que les appels à Google Places ne renvoient pas d'erreur (quota, clé invalide, API non activée).

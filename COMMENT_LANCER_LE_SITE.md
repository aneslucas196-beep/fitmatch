# Comment lancer le site FitMatch — guide simple

## En bref

- **En local (sur ton PC)** : tu lances le serveur avec une commande ; le site est sur `http://localhost:5000`.
- **En ligne (pour tout le monde)** : tu déploies sur un hébergeur (ex. Render). La config est prête, c’est toi qui crées le compte et connectes le projet.

Rien n’est lancé automatiquement pour toi : il faut soit lancer la commande en local, soit déployer sur un hébergeur.

---

## 1. Lancer le site en local (ton PC)

À faire une fois :

1. **Python 3.10+** installé.
2. **PostgreSQL** installé et une base créée (ex. `fitmatch`).
3. **Fichier `.env`** à la racine du projet (copie `.env.example` et remplis au moins `DATABASE_URL`, `RESEND_API_KEY`, `SENDER_EMAIL`).
4. **Dépendances** :
   ```bat
   install.bat
   ```
   ou :
   ```bash
   python -m pip install -r requirements.txt
   ```

Ensuite, pour lancer le site **et** les rappels (tout en un) :

```bat
python start_server.py
```

Ou :

```bat
uvicorn main:app --host 0.0.0.0 --port 5000
```

- **Site** : http://localhost:5000  
- **API / docs** : http://localhost:5000/docs  

Tu arrêtes avec `Ctrl+C`. C’est tout pour « lancer le site » en local.

---

## 2. Mettre le site en ligne (pour tout le monde)

Tu as **une** app (FastAPI + templates) à héberger. Les fichiers du projet sont déjà prêts pour deux façons de faire.

### Option A — Render (recommandé, le plus simple)

- **Ce qui est déjà fait** : le fichier `render.yaml` est prêt (service web + worker pour les rappels).
- **Ce qu’il te reste à faire** :
  1. Créer un compte sur [render.com](https://render.com).
  2. Connecter ton repo GitHub (le projet FitMatch).
  3. Créer une base PostgreSQL sur Render (ou ailleurs) et noter l’URL.
  4. Créer un **Web Service** (Render peut proposer d’utiliser `render.yaml` → Blueprint), ou créer à la main :
     - Build : `pip install -r requirements.txt`
     - Start : `uvicorn main:app --host 0.0.0.0 --port $PORT`
  5. Dans le dashboard Render, ajouter les **variables d’environnement** (comme dans `.env`) : `DATABASE_URL`, `RESEND_API_KEY`, `SENDER_EMAIL`, Stripe, etc.
  6. (Optionnel) Ajouter le **Background Worker** pour les rappels 24h/2h (défini dans `render.yaml`).

Après le déploiement, Render te donne une URL du type `https://fitmatch-xxx.onrender.com` : c’est ton site en ligne.

### Option B — Ton propre serveur (VPS Linux)

- **Ce qui est déjà fait** : `start.sh`, `start.bat`, `fitmatch.service` (systemd), voir **DEPLOIEMENT_24H.md**.
- **Ce qu’il te reste à faire** : avoir un VPS, y installer Python, PostgreSQL, cloner le repo, configurer `.env`, puis lancer avec `./start.sh` ou avec le service systemd (détails dans DEPLOIEMENT_24H.md).

---

## 3. Ce qui a été fait pour toi (résumé)

- **Dans le code** : le site (FastAPI) + la boucle de rappels (24h / 2h) dans la même app ; plus besoin de cron Vercel pour les rappels.
- **Scripts** : `start_server.py`, `start.bat`, `start.sh`, `stop.sh`, `install.bat`.
- **Config déploiement** : `render.yaml` (Render), `vercel.json` (uniquement pour l’ancienne route API rappels si tu l’utilises encore), `fitmatch.service` (systemd).
- **Doc** : README, DEPLOIEMENT_24H.md, ce fichier.

**Pas fait pour toi** : créer les comptes (Render, Vercel, etc.), connecter le repo, remplir les variables d’environnement sur l’hébergeur. Ça, c’est à faire une fois par toi.

---

## 4. Ce qui « manque » sur le site (fonctionnel)

Rien d’obligatoire ne manque **dans le code** pour « lancer » le site. Pour que tout marche **en production** :

- **Base de données** : `DATABASE_URL` obligatoire.
- **Paiements** : Stripe (clés + webhook) si tu veux les abonnements / paiements.
- **Emails** : Resend (`RESEND_API_KEY`, `SENDER_EMAIL`) pour les rappels et les mails.
- **CORS** : `CORS_ORIGINS` si un front (autre domaine) appelle l’API.

Tout est détaillé dans le README (section « Variables d'environnement » et « Checklist pré-production »).

---

## 5. Une seule chose à retenir

- **« Je veux juste voir le site »** → en local : `python start_server.py` (avec PostgreSQL + `.env`), puis ouvre http://localhost:5000.
- **« Je veux que le site soit en ligne »** → héberge sur Render (ou un VPS) une fois, avec les variables d’environnement ; après, tu n’as plus à « lancer » quoi que ce soit, c’est toujours en ligne.

Si tu veux, on peut faire ensemble uniquement la partie « Render » ou uniquement « lancer en local » étape par étape.

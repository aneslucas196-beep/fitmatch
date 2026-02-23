# Lancer FitMatch 24/7 (sans Render)

Le serveur fait tourner le site **et** l’envoi des rappels (24h / 2h) en continu.

## 1. Avec les scripts (rapide)

**Linux / Mac :**
```bash
chmod +x start.sh stop.sh
./start.sh          # premier plan (Ctrl+C pour arrêter)
./start.sh --bg     # arrière-plan (log dans fitmatch.log)
./stop.sh           # arrête si lancé avec --bg
```

**Windows :** double-clic sur `start.bat` ou en terminal : `python start_server.py`

## 2. Avec systemd (recommandé sur un VPS Linux)

Le service redémarre tout seul en cas de crash.

1. Copier le fichier service (adapter le chemin et l’utilisateur) :
   ```bash
   sudo cp fitmatch.service /etc/systemd/system/
   ```

2. Éditer pour mettre **ton** chemin et **ton** user :
   ```bash
   sudo nano /etc/systemd/system/fitmatch.service
   ```
   Modifier au minimum :
   - `User=` et `Group=` (ton user Linux, ex. `ubuntu` ou `deploy`)
   - `WorkingDirectory=` (chemin du projet, ex. `/home/ubuntu/fitmatch`)
   - `EnvironmentFile=` (ex. `/home/ubuntu/fitmatch/.env`)
   - `ExecStart=` (ex. `/usr/bin/python3 /home/ubuntu/fitmatch/start_server.py`)

3. Activer et démarrer :
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable fitmatch
   sudo systemctl start fitmatch
   ```

4. Vérifier :
   ```bash
   sudo systemctl status fitmatch
   journalctl -u fitmatch -f
   ```

## 3. Variables d’environnement

À définir dans `.env` ou dans le fichier indiqué par `EnvironmentFile` :

- `DATABASE_URL` (PostgreSQL)
- `RESEND_API_KEY` et `SENDER_EMAIL` (emails / rappels)
- Optionnel : `REMINDERS_INTERVAL_SEC=60` (intervalle en secondes entre chaque passage de rappels)
- Optionnel : `PORT=5000`

Une fois le serveur lancé (script ou systemd), les rappels et emails partent automatiquement.

## Test rapide (après `pip install -r requirements.txt`)

```bash
set DATABASE_URL=postgresql://localhost:5432/test
python test_reminders_ready.py
```
Si tout est OK, le script affiche « OK - Tout est pret » et tu peux lancer `python start_server.py`.

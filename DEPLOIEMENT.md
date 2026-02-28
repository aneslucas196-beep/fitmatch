# Commandes de déploiement FitMatch

## 1. Prérequis

- Git installé
- Compte Render configuré
- Variables d'environnement définies dans le dashboard Render

---

## 2. Déploiement sur Render (via Git)

### Option A : Push sur le dépôt (déploiement automatique)

```powershell
cd c:\Users\bendh\Downloads\project-1

# Vérifier les modifications
git status

# Ajouter les fichiers modifiés
git add db_service.py main.py templates/coach_portal.html SUPABASE_CREATE_TABLE.md migrations/003_add_working_hours.sql

# Commit
git commit -m "Fix: working_hours en DB, lien copier, dashboard coach"

# Push vers origin (déclenche le déploiement Render)
git push origin main
```

### Option B : Déploiement manuel (Render Dashboard)

1. Aller sur [dashboard.render.com](https://dashboard.render.com)
2. Sélectionner le service **fitmatch-web**
3. Cliquer sur **Manual Deploy** → **Deploy latest commit**

---

## 3. Migration Supabase (OBLIGATOIRE avant déploiement)

1. Ouvrir **Supabase** → ton projet → **SQL Editor**
2. Exécuter :

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS working_hours TEXT;
```

3. Vérifier : la colonne `working_hours` doit apparaître dans la table `users`

---

## 4. Test local avant déploiement

```powershell
cd c:\Users\bendh\Downloads\project-1

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application (avec DATABASE_URL si PostgreSQL)
$env:DATABASE_URL = "postgresql://..."  # Optionnel pour test local
python run_render.py
```

Ou avec uvicorn directement :
```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## 5. Vérification post-déploiement

1. **Dashboard coach** : Se connecter, tester "Copier le lien", durée de séance, disponibilités
2. **Réservation** : Vérifier que les clients peuvent réserver
3. **Logs Render** : Vérifier l'absence d'erreurs 401/500

---

## 6. Commandes utiles

```powershell
# Voir les logs Render (CLI)
render logs -s fitmatch-web

# Tests unitaires
pytest tests/ -v
```

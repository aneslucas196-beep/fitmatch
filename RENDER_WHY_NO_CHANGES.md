# Pourquoi rien ne change sur Render ?

**Render ne voit que le code qui est dans ton dépôt Git (GitHub, etc.).**

Toutes les modifications qu’on a faites (Stripe 30€, page abonnement, corrections) sont dans ton dossier local (`project-1`). Tant que tu ne **commites** et **pushes** pas ce code vers le dépôt connecté à Render, Render continue de déployer l’**ancienne** version.

---

## Ce qu’il faut faire (obligatoire)

### 1. Vérifier que le projet est bien un dépôt Git

Ouvre un terminal dans le dossier du projet (ex. `C:\Users\bendh\Downloads\project-1`) et exécute :

```bash
git status
```

- Si tu vois la liste des fichiers modifiés → c’est un dépôt Git, passe à l’étape 2.
- Si tu vois `fatal: not a git repository` → le dossier n’est pas un dépôt Git. Il faut soit :
  - **Option A :** Cloner le dépôt que Render utilise (depuis le dashboard Render : repo GitHub), puis **copier** tes fichiers modifiés dedans, puis commit + push.
  - **Option B :** Initialiser Git ici et connecter ce dossier à ton repo GitHub, puis push (voir plus bas).

### 2. Envoyer les changements vers GitHub (ou le repo connecté à Render)

Dans le même dossier, exécute :

```bash
git add .
git commit -m "Stripe 30€, corrections abo coach, nettoyage demo"
git push origin main
```

(Remplace `main` par le nom de ta branche si ce n’est pas `main`, par ex. `master`.)

- Si `git push` te demande un login : connecte-toi à GitHub (ou au service où est hébergé le repo).
- Si le repo n’a pas encore de “remote” : il faut d’abord le connecter à GitHub (voir option B ci‑dessous).

### 3. Déclencher un déploiement sur Render

- Soit Render fait un **auto-deploy** à chaque push → attends 2–5 minutes et recharge ton site.
- Soit le déploiement est manuel : dans le **dashboard Render** → ton **Web Service** → **Manual Deploy** → **Deploy latest commit**.

---

## Si le dossier n’est pas encore un dépôt Git (option B)

1. Crée un **nouveau dépôt** sur GitHub (vide, sans README).
2. Dans ton dossier `project-1` :

```bash
git init
git add .
git commit -m "Initial commit FitMatch"
git branch -M main
git remote add origin https://github.com/TON-USERNAME/TON-REPO.git
git push -u origin main
```

(Remplace `TON-USERNAME` et `TON-REPO` par ton compte et le nom du repo.)

3. Sur **Render** : connecte ce repo GitHub au Web Service (si ce n’est pas déjà fait) et déploie.

---

## Résumé

| Où est le code ?           | Render le voit ? |
|----------------------------|------------------|
| Uniquement sur ton PC      | Non              |
| Poussé sur GitHub (ou Git)| Oui, après push  |

Donc : **tant que tu ne fais pas `git add` → `git commit` → `git push`**, Render ne peut pas déployer les dernières modifications. Dès que tu pushes, Render utilise le dernier commit et les changements apparaissent après le déploiement.

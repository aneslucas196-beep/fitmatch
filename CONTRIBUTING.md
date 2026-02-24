# Guide de contribution – FitMatch

Merci de contribuer à FitMatch. Ce document décrit comment participer au projet.

## Prérequis

- Python 3.10+
- PostgreSQL (optionnel en local, requis en production)

## Installation en développement

```bash
# Cloner le dépôt
git clone https://github.com/votre-org/fitmatch.git
cd fitmatch

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou: .venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements-dev.txt

# Copier la configuration
cp .env.example .env
# Éditer .env avec vos clés (optionnel en local)
```

## Structure du projet

```
fitmatch/
├── api/           # Cron, rappels
├── routes/        # Routes modulaires (auth, payment, system, pages)
├── models/        # Schémas Pydantic
├── tests/         # Tests pytest
├── templates/     # Templates Jinja2
├── static/        # Assets statiques
└── main.py        # Application FastAPI
```

## Lancer les tests

```bash
# Tous les tests
pytest tests/ -v

# Avec couverture
pytest tests/ -v --cov=. --cov-report=term-missing

# Un fichier spécifique
pytest tests/test_auth.py -v
```

## Formatage du code

```bash
# Formater avec black
black .

# Trier les imports avec isort
isort .
```

## Vérifier les vulnérabilités

```bash
pip-audit
```

## Bonnes pratiques

1. **Branches** : créer une branche `feature/ma-fonctionnalite` ou `fix/correction`
2. **Commits** : messages clairs en français ou anglais
3. **Tests** : ajouter des tests pour les nouvelles fonctionnalités
4. **Types** : utiliser les type hints Python
5. **Logging** : utiliser `log` (pas `print`) dans le code applicatif

## Pull requests

1. S'assurer que les tests passent
2. Formater le code (black, isort)
3. Décrire les changements dans la PR
4. Attendre la revue

## Questions

Ouvrir une issue sur GitHub ou contacter l'équipe.

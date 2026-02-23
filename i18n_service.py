"""
Service d'internationalisation (i18n) pour FitMatch
Gère le chargement des traductions et la détection de langue
"""
import json
import os
from typing import Optional, Dict, Any
from functools import lru_cache

# Langues supportées
SUPPORTED_LOCALES = ['fr', 'en', 'es', 'ar', 'de', 'it', 'pt']
DEFAULT_LOCALE = 'fr'
COOKIE_NAME = 'fitmatch_locale'

# Cache des traductions
_translations_cache: Dict[str, Dict[str, Any]] = {}

def load_translations(locale: str) -> Dict[str, Any]:
    """Charge les traductions pour une langue donnée."""
    if locale in _translations_cache:
        return _translations_cache[locale]
    
    translations_path = os.path.join(os.path.dirname(__file__), 'translations', f'{locale}.json')
    
    try:
        with open(translations_path, 'r', encoding='utf-8') as f:
            translations = json.load(f)
            _translations_cache[locale] = translations
            return translations
    except FileNotFoundError:
        print(f"[WARN] Fichier de traduction non trouve: {locale}.json")
        # Fallback vers l'anglais
        if locale != DEFAULT_LOCALE:
            return load_translations(DEFAULT_LOCALE)
        return {}
    except json.JSONDecodeError as e:
        print(f"[ERR] Erreur JSON dans {locale}.json: {e}")
        return {}

def get_preferred_locale(accept_language: Optional[str]) -> str:
    """
    Extrait la langue préférée depuis le header Accept-Language.
    Fonctionne avec le navigateur intégré Instagram (iOS/Android).
    """
    if not accept_language:
        return DEFAULT_LOCALE
    
    # Parse le header Accept-Language (ex: "fr-FR,fr;q=0.9,en;q=0.8")
    languages = []
    for lang in accept_language.split(','):
        parts = lang.strip().split(';q=')
        code = parts[0].split('-')[0].lower()  # "fr-FR" → "fr"
        priority = float(parts[1]) if len(parts) > 1 else 1.0
        languages.append((code, priority))
    
    # Trier par priorité (plus haute en premier)
    languages.sort(key=lambda x: x[1], reverse=True)
    
    # Trouver la première langue supportée
    for code, _ in languages:
        if code in SUPPORTED_LOCALES:
            return code
    
    return DEFAULT_LOCALE

def get_locale_from_request(request) -> str:
    """
    Détermine la langue pour une requête.
    Priorité: Query lang= > Cookie > Path > Accept-Language > Défaut
    """
    # 1. Paramètre de requête ?lang= (permet de forcer la langue sur les pages légales/contact)
    query_locale = request.query_params.get("lang") if hasattr(request, "query_params") else None
    if query_locale and query_locale in SUPPORTED_LOCALES:
        return query_locale
    
    # 2. Cookie
    cookie_locale = request.cookies.get(COOKIE_NAME)
    if cookie_locale and cookie_locale in SUPPORTED_LOCALES:
        return cookie_locale
    
    # 3. Préfixe dans l'URL (ex: /fr/coach/...)
    path = request.url.path
    path_parts = path.strip('/').split('/')
    if path_parts and path_parts[0] in SUPPORTED_LOCALES:
        return path_parts[0]
    
    # 4. Header Accept-Language
    accept_language = request.headers.get('accept-language')
    return get_preferred_locale(accept_language)

def get_translations(locale: str) -> Dict[str, Any]:
    """Retourne les traductions pour une langue."""
    if locale not in SUPPORTED_LOCALES:
        locale = DEFAULT_LOCALE
    return load_translations(locale)

def t(translations: Dict[str, Any], key: str, default: str = '') -> str:
    """
    Récupère une traduction par clé avec notation pointée.
    Exemple: t(translations, 'home.hero_title')
    """
    keys = key.split('.')
    value = translations
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default or key
    
    return value if isinstance(value, str) else default or key

# Précharger toutes les traductions au démarrage
def preload_all_translations():
    """Précharge toutes les traductions en mémoire."""
    for locale in SUPPORTED_LOCALES:
        load_translations(locale)
    print(f"[OK] Traductions prechargees: {', '.join(SUPPORTED_LOCALES)}")

# Liste des langues disponibles pour le sélecteur
def get_available_languages() -> list:
    """Retourne la liste des langues disponibles avec leurs noms."""
    languages = []
    for locale in SUPPORTED_LOCALES:
        translations = load_translations(locale)
        languages.append({
            'code': locale,
            'name': translations.get('lang_name', locale.upper()),
            'dir': translations.get('dir', 'ltr')
        })
    return languages

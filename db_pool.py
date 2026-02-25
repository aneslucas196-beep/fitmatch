"""
Pool de connexions PostgreSQL pour FitMatch.
Évite l'erreur Supabase "MaxClientsInSessionMode: max clients reached".
- Utilise le pooler Supabase (port 6543, Transaction mode) au lieu du port direct 5432.
- ThreadedConnectionPool (thread-safe) avec maxconn=5 pour rester sous la limite Supabase gratuite.
"""
import os
import re
from psycopg2.pool import ThreadedConnectionPool

# DATABASE_URL depuis l'environnement (jamais hardcodé)
_RAW_URL = os.environ.get("DATABASE_URL")
_CONNECT_TIMEOUT = int(os.environ.get("DATABASE_CONNECT_TIMEOUT", "10"))
_MIN_POOL = int(os.environ.get("DB_POOL_MIN", "1"))
_MAX_POOL = min(int(os.environ.get("DB_POOL_MAX", "5")), 5)  # max 5 pour Supabase gratuit

# Conversion Supabase : port 5432 (Session) -> 6543 (Transaction/pooler)
# Évite "MaxClientsInSessionMode: max clients reached"
def _get_pooler_url(url: str) -> str:
    if not url or "supabase" not in url.lower():
        return url
    # Remplacer :5432/ par :6543/ pour utiliser le pooler
    if ":5432/" in url or ":5432?" in url or url.rstrip("/").endswith(":5432"):
        url = re.sub(r":5432(/|\?|$)", r":6543\1", url)
    return url

DATABASE_URL = _get_pooler_url(_RAW_URL) if _RAW_URL else None

_connection_pool = None


def _get_pool():
    """Crée le pool au premier usage (lazy init)."""
    global _connection_pool
    if _connection_pool is None and DATABASE_URL:
        try:
            _connection_pool = ThreadedConnectionPool(
                minconn=_MIN_POOL,
                maxconn=_MAX_POOL,
                dsn=DATABASE_URL,
                connect_timeout=_CONNECT_TIMEOUT,
            )
        except Exception as e:
            from logger import get_logger
            get_logger().error(f"[db_pool] Erreur création pool: {e}")
    return _connection_pool


def get_connection():
    """Obtient une connexion depuis le pool. Toujours appeler release_connection après usage."""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL non configuré")
    pool = _get_pool()
    if pool is None:
        raise Exception("Pool de connexions non initialisé (DATABASE_URL absent)")
    return pool.getconn()


def release_connection(conn):
    """Rend une connexion au pool. À appeler systématiquement après chaque usage."""
    if conn is None:
        return
    pool = _get_pool()
    if pool:
        try:
            pool.putconn(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
    else:
        try:
            conn.close()
        except Exception:
            pass

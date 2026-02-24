"""
Utilitaires de retry pour les appels API externes.
"""
import time
from typing import Callable, TypeVar, Optional

T = TypeVar("T")

def retry_on_failure(
    fn: Callable[[], T],
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> T:
    """
    Execute fn avec retry en cas d'echec.
    delay: delai initial en secondes
    backoff: multiplicateur entre chaque tentative
    """
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except exceptions as e:
            last_exc = e
            if attempt < max_attempts - 1:
                time.sleep(delay)
                delay *= backoff
    raise last_exc

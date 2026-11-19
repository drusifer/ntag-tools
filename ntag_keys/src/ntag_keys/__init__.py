"""ntag_keys: tag key model and key stores.

Default install has no dependencies and gives the CSV store. The k3s store needs the extra:
    pip install ntag-keys[k3s]
"""

from .base import CounterStoreError, KeyConflictError, TagKeyStore
from .csv_store import CsvSecretStore
from .factory import BACKENDS, create_secret_store
from .memory_store import MemorySecretStore
from .models import TagSecret

__version__ = "0.3.1"


def __getattr__(name: str):
    if name == "K3sSecretStore":
        from .k3s_store import K3sSecretStore

        return K3sSecretStore
    raise AttributeError(name)


__all__ = [
    "BACKENDS",
    "CounterStoreError",
    "CsvSecretStore",
    "K3sSecretStore",
    "KeyConflictError",
    "MemorySecretStore",
    "TagKeyStore",
    "TagSecret",
    "create_secret_store",
]

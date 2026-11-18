"""Compatibility shim: key stores live in ntag_keys."""

from ntag_keys import (  # noqa: F401
    CounterStoreError,
    CsvSecretStore,
    KeyConflictError,
    MemorySecretStore,
    TagKeyStore,
    create_secret_store,
)


def __getattr__(name: str):
    if name == "K3sSecretStore":
        from ntag_keys.k3s_store import K3sSecretStore

        return K3sSecretStore
    raise AttributeError(name)

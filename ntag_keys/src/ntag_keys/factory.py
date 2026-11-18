"""Key store factory. CSV is the default backend."""

from __future__ import annotations

from .base import TagKeyStore

BACKENDS = ("csv", "memory", "k3s")


def create_secret_store(
    backend: str = "csv",
    namespace: str = "tag-secrets",
    kubeconfig_path: str | None = None,
    csv_path: str = "tag_keys.csv",
) -> TagKeyStore:
    """Create the key store for `backend` (csv | memory | k3s)."""
    b = (backend or "csv").lower()
    if b in ("k3s", "k8s", "kubernetes"):
        from .k3s_store import K3sSecretStore

        return K3sSecretStore(namespace=namespace, kubeconfig_path=kubeconfig_path)
    if b == "memory":
        from .memory_store import MemorySecretStore

        return MemorySecretStore()
    if b == "csv":
        from .csv_store import CsvSecretStore

        return CsvSecretStore(csv_path)
    raise ValueError(f"Unknown key store backend '{backend}'. Allowed: {', '.join(BACKENDS)}")

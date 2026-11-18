"""Key manager that saves a tag's keys straight into a key store (CSV default, k3s optional).

The provisioner generates keys itself (CSPRNG), saves them through the same store code the
validator reads with, and reads them back to resume a half-written tag. Keys never travel over HTTP
and are never logged. The store knows tags only: no coin names, sides or outcomes.
"""

from __future__ import annotations

import logging
import os
import secrets
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from tag_validator.crypto.cmac_engine import verify_sdm_cmac

from ntag_keys import (
    KeyConflictError,
    MemorySecretStore,
    TagKeyStore,
    TagSecret,
    create_secret_store,
)
from sdm_provisioner.key_manager import KeyManager
from shared import UID, TagKeys

log = logging.getLogger(__name__)

FACTORY_KEY = "0" * 32
STORE_CHOICES = ("csv", "k3s", "memory")


class KeyStoreError(RuntimeError):
    """The key store could not be used; says which store and where."""


def _uid_str(uid: UID | bytes | str) -> str:
    if isinstance(uid, UID):
        return uid.uid
    if isinstance(uid, (bytes, bytearray)):
        return bytes(uid).hex().upper()
    return str(uid).strip().replace(":", "").replace("-", "").upper()


class StoreKeyManager(KeyManager):
    """Provisioner-side key manager over a `ntag_keys.TagKeyStore`."""

    def __init__(self, store: TagKeyStore) -> None:
        self.store = store

    @classmethod
    def from_env(cls) -> StoreKeyManager:
        """Build from NTAG_KEY_STORE (csv|k3s, default csv), NTAG_KEY_CSV, NTAG_K3S_NAMESPACE, KUBECONFIG."""
        backend = os.environ.get("NTAG_KEY_STORE", "csv").strip().lower()
        if backend not in STORE_CHOICES:
            raise ValueError(
                f"Invalid NTAG_KEY_STORE '{backend}'. Allowed values: {', '.join(STORE_CHOICES)}."
            )
        store = create_secret_store(
            backend=backend,
            namespace=os.environ.get("NTAG_K3S_NAMESPACE", "tag-secrets"),
            kubeconfig_path=os.environ.get("KUBECONFIG") or None,
            csv_path=os.environ.get("NTAG_KEY_CSV", "tag_keys.csv"),
        )
        return cls(store)

    # ── where keys live ──────────────────────────────────────────────────────

    @property
    def location(self) -> str:
        path = getattr(self.store, "path", None)
        if path is not None:
            return str(path)
        ns = getattr(self.store, "namespace", None)
        return f"k3s namespace {ns}" if ns else "memory"

    @property
    def description(self) -> str:
        return f"{type(self.store).__name__} at {self.location}"

    @property
    def is_persistent(self) -> bool:
        return not isinstance(self.store, MemorySecretStore)

    # Compatibility names used by loggers and tools.
    @property
    def csv_path(self) -> str:
        return self.location

    @property
    def backup_path(self) -> str:
        return self.location

    def is_healthy(self) -> bool:
        return self.store.is_healthy()

    def _fail(self, action: str, uid: str, err: Exception) -> KeyStoreError:
        return KeyStoreError(f"Cannot {action} keys for {uid} in {self.description}: {err}")

    # ── KeyManager protocol ──────────────────────────────────────────────────

    def get_key_for_uid(self, uid: bytes, key_no: int) -> bytes:
        return self.get_key(uid, key_no)

    def get_key(self, uid: UID | bytes | str, key_no: int) -> bytes:
        if key_no < 0 or key_no > 4:
            raise ValueError(f"Key number must be 0-4, got {key_no}")
        if key_no in (2, 4):
            return b"\x00" * 16
        secret = self._get(_uid_str(uid))
        if secret is None:
            return b"\x00" * 16
        return bytes.fromhex({0: secret.k0, 1: secret.k1, 3: secret.k3}[key_no])

    def _get(self, uid: str, include_deleted: bool = False) -> TagSecret | None:
        try:
            return self.store.get_key(uid, include_deleted=include_deleted)
        except Exception as e:
            raise self._fail("read", uid, e) from e

    # ── tag keys ─────────────────────────────────────────────────────────────

    @staticmethod
    def _to_tag_keys(uid: UID, s: TagSecret, notes: str = "Stored in key store") -> TagKeys:
        return TagKeys(
            uid=uid,
            picc_master_key=s.k0,
            app_read_key=s.k1,
            sdm_mac_key=s.k3,
            provisioned_date=s.created_at,
            status=s.status,
            notes=notes,
        )

    def get_tag_keys(self, uid: UID | str) -> TagKeys:
        uid_obj = uid if isinstance(uid, UID) else UID(str(uid))
        secret = self._get(uid_obj.uid)
        if secret is None:
            return TagKeys.from_factory_keys(uid_obj)
        return self._to_tag_keys(uid_obj, secret)

    def save_tag_keys(self, tag_keys: TagKeys) -> bool:
        """Store non-factory keys. Factory keys are not stored (nothing to remember)."""
        k3 = tag_keys.sdm_mac_key
        if not k3 or k3 == FACTORY_KEY or "..." in k3:
            return True
        uid = tag_keys.uid.uid
        secret = TagSecret(
            uid=uid,
            k3=k3,
            k0=tag_keys.picc_master_key or FACTORY_KEY,
            k1=tag_keys.app_read_key or FACTORY_KEY,
            status="deleted" if tag_keys.status == "deleted" else "active",
        )
        try:
            return self.store.save_key(secret)
        except KeyConflictError as e:
            raise KeyStoreError(
                f"Keys for {uid} are immutable in {self.description}: a different key is already "
                "stored. Delete the tag's key first if you really mean to replace it."
            ) from e
        except Exception as e:
            raise self._fail("save", uid, e) from e

    def generate_random_keys(self, uid: UID | str) -> TagKeys:
        """Generate fresh CSPRNG keys and store them before returning."""
        uid_obj = uid if isinstance(uid, UID) else UID(str(uid))
        keys = TagKeys(
            uid=uid_obj,
            picc_master_key=secrets.token_hex(16).upper(),
            app_read_key=secrets.token_hex(16).upper(),
            sdm_mac_key=secrets.token_hex(16).upper(),
            provisioned_date=datetime.now(UTC).isoformat(),
            status="provisioned",
            notes="Generated locally and stored in key store",
        )
        self.save_tag_keys(keys)
        return keys

    # ── two-phase provisioning ───────────────────────────────────────────────

    @contextmanager
    def provision_tag(self, uid: UID | str, url: str | None = None):
        """Phase 1 (url=None) stores/loads the tag's keys; phase 2 (url given) marks it active.

        Keys are in the store before the tag is touched. If the store cannot be used, this
        raises KeyStoreError before yielding. A failed run keeps the keys so it can resume.
        """
        uid_obj = uid if isinstance(uid, UID) else UID(str(uid))
        if not self.store.is_healthy():
            raise KeyStoreError(f"Key store not usable: {self.description}. Nothing was written to the tag.")
        existing = self._get(uid_obj.uid)
        if existing is not None:
            staged = self._to_tag_keys(uid_obj, existing, notes="Provisioning in progress...")
        else:
            staged = self.generate_random_keys(uid_obj)
            staged.notes = "Provisioning in progress..."
        staged.status = "pending"

        yield staged

        staged.status = "keys_configured" if url is None else "active"
        staged.notes = url or "Keys configured, ready for URL provisioning"
        self.save_tag_keys(staged)

    @contextmanager
    def update_url(self, uid: UID | str, url: str):
        uid_obj = uid if isinstance(uid, UID) else UID(str(uid))
        tag_keys = self.get_tag_keys(uid_obj)
        yield tag_keys
        tag_keys.status = "active"
        tag_keys.notes = url
        self.save_tag_keys(tag_keys)

    # ── validation, listing, housekeeping ────────────────────────────────────

    def validate_sdm_url(self, uid: UID | str, counter: int, cmac: str) -> dict[str, Any]:
        uid_obj = uid if isinstance(uid, UID) else UID(str(uid))
        secret = self._get(uid_obj.uid)
        if secret is None:
            return {"valid": False, "uid": uid_obj, "counter": counter, "cmac_received": cmac,
                    "cmac_calculated": None, "error": "No keys stored for this tag"}
        ok, calculated = verify_sdm_cmac(uid_obj.uid, counter, secret.k3, cmac)
        return {"valid": ok, "uid": uid_obj, "counter": counter, "cmac_received": cmac,
                "cmac_calculated": calculated, "error": None}

    def list_tags(self) -> list[TagKeys]:
        try:
            uids = self.store.list_uids(include_deleted=True)
        except Exception as e:
            raise self._fail("list", "all tags", e) from e
        out = []
        for u in uids:
            s = self._get(u, include_deleted=True)
            if s is not None:
                out.append(self._to_tag_keys(UID(u), s))
        return out

    def delete_key(self, uid: UID | str) -> bool:
        return self.store.delete_key(_uid_str(uid))

    def undelete_key(self, uid: UID | str) -> bool:
        return self.store.undelete_key(_uid_str(uid))

    def get_backup_entries(self, uid: UID) -> list[TagKeys]:
        """No separate backups: the store is write-once, so earlier keys are never overwritten."""
        return []

    def restore_from_backup(self, uid: UID) -> TagKeys | None:
        return None

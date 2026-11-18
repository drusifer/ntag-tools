"""CSV key store: the default. One file of tag keys, one sibling file of counters.

Safe to share between processes (the provisioner writes, the validator reads): every operation
re-reads the file under an advisory lock, and writes go through a temp file and an atomic rename.
There are no coin, side or outcome columns; this store is about tags only.
"""

from __future__ import annotations

import csv
import os
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .base import CounterStoreError, KeyConflictError, TagKeyStore
from .models import TagSecret

try:
    import fcntl
except ImportError:  # Windows: thread lock only
    fcntl = None  # type: ignore[assignment]

COLUMNS = ["uid", "k0", "k1", "k3", "status", "created_at", "deleted_at"]
COUNTER_COLUMNS = ["uid", "counter"]


def _clean(uid: str) -> str:
    return uid.strip().replace(":", "").replace("-", "").upper()


class CsvSecretStore(TagKeyStore):
    """Tag keys in a CSV file with WORM and soft-delete semantics."""

    def __init__(self, path: str | os.PathLike = "tag_keys.csv", create_dirs: bool = True) -> None:
        super().__init__()
        self.path = Path(path)
        self.counter_path = self.path.with_suffix(".counters.csv")
        self._lock_path = self.path.with_suffix(".lock")
        self._tlock = threading.RLock()
        if create_dirs:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    # ── file plumbing ────────────────────────────────────────────────────────

    @contextmanager
    def _locked(self):
        with self._tlock:
            fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                if fcntl is not None:
                    fcntl.flock(fd, fcntl.LOCK_EX)
                yield
            finally:
                os.close(fd)

    def _read(self) -> dict[str, TagSecret]:
        if not self.path.exists():
            return {}
        out: dict[str, TagSecret] = {}
        with open(self.path, newline="", encoding="utf-8") as f:
            for lineno, row in enumerate(csv.DictReader(f), start=2):
                try:
                    out[_clean(row["uid"])] = TagSecret(
                        uid=row["uid"],
                        k0=row["k0"],
                        k1=row["k1"],
                        k3=row["k3"],
                        status=row.get("status") or "active",
                        created_at=row.get("created_at") or datetime.now(UTC).isoformat(),
                        deleted_at=row.get("deleted_at") or None,
                    )
                except (KeyError, ValueError, TypeError) as e:
                    raise ValueError(f"{self.path}: bad row at line {lineno}: {e}") from e
        return out

    def _atomic_write(self, path: Path, header: list[str], rows: list[list[str]]) -> None:
        tmp = path.with_name(path.name + f".tmp{os.getpid()}")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(header)
                w.writerows(rows)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except OSError as e:
            raise OSError(f"cannot write key store file {path}: {e}") from e
        finally:
            if tmp.exists():
                tmp.unlink()

    def _write(self, secrets: dict[str, TagSecret]) -> None:
        rows = [
            [s.uid, s.k0, s.k1, s.k3, s.status, s.created_at, s.deleted_at or ""]
            for s in sorted(secrets.values(), key=lambda s: s.uid)
        ]
        self._atomic_write(self.path, COLUMNS, rows)

    # ── TagKeyStore ──────────────────────────────────────────────────────────

    def get_key(self, uid: str, include_deleted: bool = False) -> TagSecret | None:
        with self._locked():
            s = self._read().get(_clean(uid))
        if s is None or (s.status == "deleted" and not include_deleted):
            return None
        return s

    def save_key(self, secret: TagSecret) -> bool:
        with self._locked():
            all_ = self._read()
            existing = all_.get(secret.uid)
            if existing is not None:
                if (existing.k0, existing.k1, existing.k3) != (secret.k0, secret.k1, secret.k3):
                    raise KeyConflictError(
                        f"Tag key for UID '{secret.uid}' is immutable and cannot be overwritten "
                        "with a different key."
                    )
                existing.status = secret.status
                existing.deleted_at = secret.deleted_at
            else:
                all_[secret.uid] = secret
            self._write(all_)
        return True

    def _set_status(self, uid: str, status: str, deleted_at: str | None) -> bool:
        with self._locked():
            all_ = self._read()
            s = all_.get(_clean(uid))
            if s is None:
                return False
            s.status, s.deleted_at = status, deleted_at
            self._write(all_)
        return True

    def delete_key(self, uid: str) -> bool:
        return self._set_status(uid, "deleted", datetime.now(UTC).isoformat())

    def undelete_key(self, uid: str) -> bool:
        return self._set_status(uid, "active", None)

    def list_uids(self, include_deleted: bool = False) -> list[str]:
        with self._locked():
            all_ = self._read()
        return sorted(u for u, s in all_.items() if include_deleted or s.status == "active")

    def consume_counter(self, uid: str, counter: int) -> bool:
        key = _clean(uid)
        try:
            with self._locked():
                counters: dict[str, int] = {}
                if self.counter_path.exists():
                    with open(self.counter_path, newline="", encoding="utf-8") as f:
                        for row in csv.DictReader(f):
                            counters[row["uid"]] = int(row["counter"])
                if counter <= counters.get(key, -1):
                    return False
                counters[key] = counter
                self._atomic_write(
                    self.counter_path,
                    COUNTER_COLUMNS,
                    [[u, str(c)] for u, c in sorted(counters.items())],
                )
                return True
        except (OSError, ValueError, KeyError) as e:
            raise CounterStoreError(f"cannot use counter file {self.counter_path}: {e}") from e

    def is_healthy(self) -> bool:
        parent = self.path.parent
        return parent.is_dir() and os.access(parent, os.W_OK)

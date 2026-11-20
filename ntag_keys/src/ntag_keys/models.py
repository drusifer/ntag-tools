"""Tag key model shared by every key store."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def key_fingerprint(key_hex: str) -> str:
    """First 8 hex characters of SHA-256 of the key bytes. One-way, so it is safe to show and log."""
    try:
        material = bytes.fromhex(key_hex)
    except ValueError:
        material = key_hex.encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:8].upper()


@dataclass
class TagSecret:
    """Represents a tag's cryptographic keys stored in k3s secrets.

    Stores Key 0 (PICC Master Key), Key 1 (App Read Key), and Key 3 (SDM MAC Key)
    per specification, with internal WORM status.
    """

    uid: str
    k3: str  # 32-character hex AES-128 key
    k0: str = "00000000000000000000000000000000"  # Key 0 (PICC Master Key)
    k1: str = "00000000000000000000000000000000"  # Key 1 (App Read Key)
    status: str = "active"  # "active" | "deleted"
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    deleted_at: str | None = None

    def __post_init__(self) -> None:
        self.uid = self.uid.strip().replace(":", "").replace("-", "").upper()
        self.k3 = self.k3.strip().replace(" ", "").upper()
        self.k0 = self.k0.strip().replace(" ", "").upper()
        self.k1 = self.k1.strip().replace(" ", "").upper()
        if len(self.uid) != 14:
            raise ValueError(f"UID must be 14 hex characters, got '{self.uid}'")
        if len(self.k3) != 32:
            raise ValueError(f"K3 must be 32 hex characters (16 bytes), got '{self.k3}'")
        if len(self.k0) != 32:
            raise ValueError(f"K0 must be 32 hex characters (16 bytes), got '{self.k0}'")
        if len(self.k1) != 32:
            raise ValueError(f"K1 must be 32 hex characters (16 bytes), got '{self.k1}'")

    @property
    def secret_name(self) -> str:
        """RFC 1123 compliant secret name for Kubernetes/k3s."""
        return f"tag-key-{self.uid.lower()}"

    def fingerprint_k3(self) -> str:
        """One-way tag for K3: tells keys apart, shows no key characters."""
        return key_fingerprint(self.k3)

    def fingerprint_k0(self) -> str:
        """One-way tag for K0: tells keys apart, shows no key characters."""
        return key_fingerprint(self.k0)

    def fingerprint_k1(self) -> str:
        """One-way tag for K1: tells keys apart, shows no key characters."""
        return key_fingerprint(self.k1)

    def to_k8s_secret_data(self) -> dict[str, str]:
        """Encodes values for Kubernetes Secret .data dictionary (base64 string values)."""
        data = {
            "uid": base64.b64encode(self.uid.encode("utf-8")).decode("utf-8"),
            "k0": base64.b64encode(self.k0.encode("utf-8")).decode("utf-8"),
            "k1": base64.b64encode(self.k1.encode("utf-8")).decode("utf-8"),
            "k3": base64.b64encode(self.k3.encode("utf-8")).decode("utf-8"),
            "status": base64.b64encode(self.status.encode("utf-8")).decode("utf-8"),
            "created_at": base64.b64encode(self.created_at.encode("utf-8")).decode("utf-8"),
        }
        if self.deleted_at:
            data["deleted_at"] = base64.b64encode(self.deleted_at.encode("utf-8")).decode("utf-8")
        return data

    @classmethod
    def from_k8s_secret_data(cls, secret_data: dict[str, Any]) -> TagSecret:
        """Decodes values from Kubernetes Secret dictionary."""
        def _decode(val: Any) -> str:
            if isinstance(val, bytes):
                return val.decode("utf-8")
            if isinstance(val, str):
                try:
                    # In k8s client, .data may be pre-decoded or raw base64
                    decoded = base64.b64decode(val.encode("utf-8")).decode("utf-8")
                    return decoded
                except Exception:
                    return val
            return str(val)

        uid = _decode(secret_data.get("uid", ""))
        k3 = _decode(secret_data.get("k3", "") or secret_data.get("sdm_mac_key", ""))
        k0 = _decode(secret_data.get("k0", "") or secret_data.get("picc_master_key", "")) or "00000000000000000000000000000000"
        k1 = _decode(secret_data.get("k1", "") or secret_data.get("app_read_key", "")) or "00000000000000000000000000000000"
        status = _decode(secret_data.get("status", "active"))
        created_at = _decode(secret_data.get("created_at", ""))
        raw_deleted_at = secret_data.get("deleted_at")
        deleted_at = _decode(raw_deleted_at) if raw_deleted_at else None

        return cls(
            uid=uid,
            k3=k3,
            k0=k0,
            k1=k1,
            status=status,
            created_at=created_at or datetime.now(UTC).isoformat(),
            deleted_at=deleted_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Metadata for JSON serialization. Never holds a key value; there is no switch for that."""
        data: dict[str, Any] = {
            "uid": self.uid,
            "secret_name": self.secret_name,
            "status": self.status,
            "created_at": self.created_at,
            "k0_fingerprint": self.fingerprint_k0(),
            "k1_fingerprint": self.fingerprint_k1(),
            "k3_fingerprint": self.fingerprint_k3(),
        }
        if self.deleted_at:
            data["deleted_at"] = self.deleted_at
        return data

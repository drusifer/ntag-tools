"""Validator data models. `TagSecret` lives in ntag_keys and is re-exported here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ntag_keys import TagSecret

__all__ = ["TagSecret", "ValidationResult"]


@dataclass
class ValidationResult:
    """Result of an SDM CMAC validation request."""

    valid: bool
    uid: str
    counter: int
    cmac_received: str
    cmac_calculated: str | None = None
    error: str | None = None
    reason: str | None = None  # "replayed" when a consuming request reused a counter
    consumed: bool | None = None  # set only on consuming requests: was the counter recorded now?

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "valid": self.valid,
            "uid": self.uid,
            "counter": self.counter,
            "cmac_received": self.cmac_received,
        }
        if self.reason:
            res["reason"] = self.reason
        if self.consumed is not None:
            res["consumed"] = self.consumed
        if self.cmac_calculated:
            res["cmac_calculated"] = self.cmac_calculated
        if self.error:
            res["error"] = self.error
        return res

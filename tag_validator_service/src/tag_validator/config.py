"""Service configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field

MODES = ("full", "validate")


def resolve_mode(value: str | None = None) -> str:
    """Return the validator mode ('full' or 'validate'); refuse anything else."""
    raw = os.getenv("TAG_VALIDATOR_MODE", "full") if value is None else value
    mode = (raw or "full").strip().lower()
    if mode not in MODES:
        raise ValueError(
            f"Invalid TAG_VALIDATOR_MODE '{raw}'. Allowed values: {', '.join(MODES)}."
        )
    return mode


@dataclass
class Config:
    """Microservice runtime configuration."""

    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8080")))
    secret_store_backend: str = field(
        default_factory=lambda: os.getenv("SECRET_STORE_BACKEND", "memory").lower()
    )
    tag_secrets_namespace: str = field(
        default_factory=lambda: os.getenv("TAG_SECRETS_NAMESPACE", "tag-secrets")
    )
    mode: str = field(default_factory=resolve_mode)
    csv_path: str = field(default_factory=lambda: os.getenv("TAG_KEYS_CSV", "tag_keys.csv"))
    kubeconfig_path: str = field(default_factory=lambda: os.getenv("KUBECONFIG", ""))
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    )


def get_config() -> Config:
    return Config()

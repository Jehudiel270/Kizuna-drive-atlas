"""Paramètres de l'application, lus dans les variables d'environnement (voir .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "oui", "on"}


def _db_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./kizuna.db").strip()
    # Neon / Render / Heroku fournissent « postgres:// » ou « postgresql:// » : on force le pilote psycopg 3
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@dataclass
class Settings:
    database_url: str = field(default_factory=_db_url)
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", "dev-secret-change-me"))
    token_ttl_hours: int = field(default_factory=lambda: int(os.getenv("TOKEN_TTL_HOURS", "12")))
    admin_email: str = field(default_factory=lambda: os.getenv("ADMIN_EMAIL", "").strip().lower())
    admin_password: str = field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", ""))
    tally_api_key: str = field(default_factory=lambda: os.getenv("TALLY_API_KEY", ""))
    tally_form_id: str = field(default_factory=lambda: os.getenv("TALLY_FORM_ID", "446dvO"))
    tally_signing_secret: str = field(default_factory=lambda: os.getenv("TALLY_SIGNING_SECRET", ""))
    email_salt: str = field(default_factory=lambda: os.getenv("EMAIL_SALT", "kizuna-dev-salt"))
    cors_origins: list[str] = field(default_factory=lambda: [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()])
    cors_origin_regex: str = field(default_factory=lambda: os.getenv("CORS_ORIGIN_REGEX", ""))
    demo_mode: bool = field(default_factory=lambda: _bool("DEMO_MODE", False))
    demo_n: int = field(default_factory=lambda: int(os.getenv("DEMO_N", "165")))
    demo_seed: int = field(default_factory=lambda: int(os.getenv("DEMO_SEED", "7")))
    tally_base: str = field(default_factory=lambda: os.getenv("TALLY_API_BASE", "https://api.tally.so"))


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> Settings:
    """Recharge les variables d'environnement (utilisé par les tests)."""
    global _settings
    _settings = Settings()
    return _settings

"""Loads nocturne.toml once and exposes it as attribute-style settings (cfg.etl.batch_size)."""
from __future__ import annotations

import os
import re
import secrets
import tomllib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("NOCTURNE_CONFIG", ROOT / "nocturne.toml"))


class Section(SimpleNamespace):
    """Namespace that also behaves like a read-only mapping."""

    def get(self, key, default=None):
        return getattr(self, str(key), default)

    def items(self):
        return vars(self).items()

    def keys(self):
        return vars(self).keys()

    def __getitem__(self, key):
        return getattr(self, str(key))

    def __contains__(self, key):
        return str(key) in vars(self)


def _wrap(value):
    if isinstance(value, dict):
        return Section(**{str(k): _wrap(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_wrap(v) for v in value]
    return value


def _coerce(raw: str, current):
    if isinstance(current, bool):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current, int):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    return raw


def _apply_env_overrides(data: dict) -> None:
    # NOCTURNE__DIAGNOSTICS__MODE=live → data["diagnostics"]["mode"] = "live"
    for key, raw in os.environ.items():
        if not key.startswith("NOCTURNE__"):
            continue
        path = [p.lower() for p in key.split("__")[1:]]
        node = data
        for part in path[:-1]:
            node = node.setdefault(part, {})
        node[path[-1]] = _coerce(raw, node.get(path[-1]))


def load() -> Section:
    with open(CONFIG_PATH, "rb") as fh:
        data = tomllib.load(fh)
    _apply_env_overrides(data)
    cfg = _wrap(data)
    # Resolve storage paths relative to the project root.
    cfg.storage.database = str((ROOT / cfg.storage.database).resolve())
    cfg.storage.uploads = str((ROOT / cfg.storage.uploads).resolve())
    Path(cfg.storage.uploads).mkdir(parents=True, exist_ok=True)
    Path(cfg.storage.database).parent.mkdir(parents=True, exist_ok=True)
    return cfg


cfg = load()


def secret(env_name: str) -> str | None:
    value = os.environ.get(env_name or "", "").strip()
    return value or None


def secret_key() -> str:
    """Session-signing key from the environment, or a generated one persisted beside the DB."""
    value = secret(cfg.security.secret_key_env)
    if value:
        return value
    path = Path(cfg.storage.database).parent / ".secret"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48))
        path.chmod(0o600)
    return path.read_text().strip()


def compiled(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


def masked_view() -> dict:
    """Effective configuration for the settings page; secret values are never included."""
    def plain(node):
        if isinstance(node, Section):
            return {k: plain(v) for k, v in vars(node).items()}
        if isinstance(node, list):
            return [plain(v) for v in node]
        return node

    data = plain(cfg)
    data["_secrets"] = {
        "session key": "environment" if secret(cfg.security.secret_key_env) else "generated file",
        "AI API key": f"configured ({cfg.ai.api_key_env})" if secret(cfg.ai.api_key_env) else f"not set ({cfg.ai.api_key_env})",
        "bootstrap admin password": "environment" if secret(cfg.security.admin_password_env) else "default (forced change)",
    }
    return data

"""Configuration loaded from environment variables.

Supports two authentication modes:
- **Token mode**: Set HOMEBOX_TOKEN directly.
- **Login mode**: Set HOMEBOX_USERNAME + HOMEBOX_PASSWORD. The server will
  authenticate on first request and refresh the token automatically on 401.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    homebox_url: str
    homebox_token: str
    homebox_username: str
    homebox_password: str
    mcp_auth_enabled: bool
    mcp_auth_token: str | None
    log_level: str
    server_host: str
    server_port: int

    @property
    def uses_login(self) -> bool:
        """True when auth is username/password rather than a static token."""
        return bool(self.homebox_username and self.homebox_password)

    @classmethod
    def from_environment(cls) -> Config:
        def _env(key: str, default: str = "") -> str:
            """Read env var, treating 'null' (bashio artifact) as empty."""
            val = os.environ.get(key, default)
            return "" if val == "null" else val

        homebox_url = _env("HOMEBOX_URL").rstrip("/")
        if not homebox_url:
            raise RuntimeError("HOMEBOX_URL environment variable is required")
        if not homebox_url.startswith(("http://", "https://")):
            raise RuntimeError(
                "HOMEBOX_URL must start with http:// or https://"
            )

        token = _env("HOMEBOX_TOKEN")
        username = _env("HOMEBOX_USERNAME")
        password = _env("HOMEBOX_PASSWORD")

        mcp_auth_enabled = _env(
            "MCP_AUTH_ENABLED", "false"
        ).lower() in ("true", "1", "yes")

        mcp_auth_token = _env("MCP_AUTH_TOKEN") or None
        if mcp_auth_enabled and not mcp_auth_token:
            raise RuntimeError(
                "MCP_AUTH_TOKEN is required when MCP_AUTH_ENABLED is true"
            )

        try:
            server_port = int(_env("SERVER_PORT", "8099"))
        except ValueError:
            server_port = 8099

        _VALID_LOG_LEVELS = {"trace", "debug", "info", "warning", "error"}
        log_level = _env("LOG_LEVEL", "info").lower()
        if log_level not in _VALID_LOG_LEVELS:
            log_level = "info"

        return cls(
            homebox_url=homebox_url,
            homebox_token=token,
            homebox_username=username,
            homebox_password=password,
            mcp_auth_enabled=mcp_auth_enabled,
            mcp_auth_token=mcp_auth_token,
            log_level=log_level,
            server_host=_env("SERVER_HOST", "0.0.0.0"),
            server_port=server_port,
        )


_config: Config | None = None


def get_config() -> Config:
    """Lazy config initialization — defers validation until first access."""
    global _config
    if _config is None:
        _config = Config.from_environment()
    return _config

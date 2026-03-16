"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    homebox_url: str
    homebox_token: str
    mcp_auth_enabled: bool
    mcp_auth_token: str | None
    log_level: str
    server_host: str
    server_port: int

    @classmethod
    def from_environment(cls) -> Config:
        token = os.environ.get("HOMEBOX_TOKEN", "")
        if not token:
            raise RuntimeError("HOMEBOX_TOKEN environment variable is required")

        homebox_url = os.environ.get("HOMEBOX_URL", "").rstrip("/")
        if not homebox_url:
            raise RuntimeError("HOMEBOX_URL environment variable is required")
        if not homebox_url.startswith(("http://", "https://")):
            raise RuntimeError(
                "HOMEBOX_URL must start with http:// or https://"
            )

        mcp_auth_enabled = os.environ.get(
            "MCP_AUTH_ENABLED", "false"
        ).lower() in ("true", "1", "yes")

        mcp_auth_token = os.environ.get("MCP_AUTH_TOKEN") or None
        if mcp_auth_enabled and not mcp_auth_token:
            raise RuntimeError(
                "MCP_AUTH_TOKEN is required when MCP_AUTH_ENABLED is true"
            )

        try:
            server_port = int(os.environ.get("SERVER_PORT", "8099"))
        except ValueError:
            server_port = 8099

        _VALID_LOG_LEVELS = {"trace", "debug", "info", "warning", "error"}
        log_level = os.environ.get("LOG_LEVEL", "info").lower()
        if log_level not in _VALID_LOG_LEVELS:
            log_level = "info"

        return cls(
            homebox_url=homebox_url,
            homebox_token=token,
            mcp_auth_enabled=mcp_auth_enabled,
            mcp_auth_token=mcp_auth_token,
            log_level=log_level,
            server_host=os.environ.get("SERVER_HOST", "0.0.0.0"),
            server_port=server_port,
        )


_config: Config | None = None


def get_config() -> Config:
    """Lazy config initialization — defers validation until first access."""
    global _config
    if _config is None:
        _config = Config.from_environment()
    return _config

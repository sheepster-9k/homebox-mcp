"""Main entry point: FastMCP server with SSE transport, auth middleware, and status dashboard."""

from __future__ import annotations

import hmac
import html
import logging
import sys

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route

from config import config

# Import tools so they get registered on the shared `mcp` instance.
from tools import mcp  # noqa: F401

logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("homebox-mcp")

# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

_PUBLIC_PATHS = frozenset({"/", "/api/status"})


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests without a valid Bearer token.

    Skipped entirely when MCP_AUTH_ENABLED is false, and always skipped
    for the public dashboard and status endpoint.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        if not config.mcp_auth_enabled:
            return await call_next(request)

        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return JSONResponse(
                {"error": "Missing bearer token"}, status_code=401
            )

        provided = auth_header[7:]  # strip "Bearer "
        expected = config.mcp_auth_token or ""

        if not hmac.compare_digest(provided.encode(), expected.encode()):
            return JSONResponse(
                {"error": "Invalid token"}, status_code=403
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# Dashboard & status
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Homebox MCP</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 600px; margin: 4rem auto; color: #222; }}
    h1 {{ font-size: 1.4rem; }}
    .ok {{ color: #16a34a; }}
    code {{ background: #f3f4f6; padding: 0.15em 0.4em; border-radius: 4px; }}
    .muted {{ color: #666; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>Homebox MCP Server</h1>
  <p class="ok">Status: running</p>
  <p>Homebox instance: <code>{homebox_url}</code></p>
  <p>Auth required: <code>{auth_enabled}</code></p>
  <p class="muted">Connect an MCP client to this server's SSE endpoint.</p>
</body>
</html>
"""


async def dashboard(request: Request) -> HTMLResponse:
    safe_url = html.escape(config.homebox_url)
    safe_auth = html.escape(str(config.mcp_auth_enabled).lower())
    body = _DASHBOARD_HTML.format(
        homebox_url=safe_url,
        auth_enabled=safe_auth,
    )
    return HTMLResponse(body)


async def api_status(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "homebox_url": config.homebox_url,
            "auth_enabled": config.mcp_auth_enabled,
        }
    )


# ---------------------------------------------------------------------------
# Application assembly
# ---------------------------------------------------------------------------


def create_app() -> Starlette:
    """Build the Starlette app with MCP mounted at root."""
    mcp_app = mcp.sse_app()

    routes = [
        Route("/", dashboard),
        Route("/api/status", api_status),
        Mount("/", app=mcp_app),
    ]

    app = Starlette(
        routes=routes,
        middleware=[Middleware(BearerAuthMiddleware)],
    )
    return app


app = create_app()

if __name__ == "__main__":
    logger.info(
        "Starting Homebox MCP on %s:%s", config.server_host, config.server_port
    )
    uvicorn.run(
        "server:app",
        host=config.server_host,
        port=config.server_port,
        log_level=config.log_level,
    )

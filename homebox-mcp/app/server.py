"""Main entry point: FastMCP server with SSE transport, auth middleware, and status dashboard."""

from __future__ import annotations

import hmac
import html
import json
import logging
import sys

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route

from config import get_config

# Import tools so they get registered on the shared `mcp` instance.
from tools import mcp  # noqa: F401
from homebox_client import client, HomeboxError

logging.basicConfig(
    level=getattr(logging, get_config().log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("homebox-mcp")

# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

_PUBLIC_PATHS = frozenset({"/", "/api/status", "/login", "/api/login"})


def _is_public_path(path: str) -> bool:
    """Check if a request path is public, normalising trailing slashes."""
    normalised = path.rstrip("/") or "/"
    return normalised in _PUBLIC_PATHS


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests without a valid Bearer token.

    Skipped entirely when MCP_AUTH_ENABLED is false, and always skipped
    for public paths (dashboard, status, login).
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        if not get_config().mcp_auth_enabled:
            return await call_next(request)

        if _is_public_path(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return JSONResponse(
                {"error": "Missing bearer token"}, status_code=401
            )

        provided = auth_header[7:]  # strip "Bearer "
        expected = get_config().mcp_auth_token or ""

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
    a {{ color: #2563eb; }}
  </style>
</head>
<body>
  <h1>Homebox MCP Server</h1>
  <p class="ok">Status: running</p>
  <p>Auth required: <code>{auth_enabled}</code></p>
  <p><a href="/login">Get Homebox API Token</a></p>
  <p class="muted">Connect an MCP client to this server's SSE endpoint.</p>
</body>
</html>
"""


async def dashboard(request: Request) -> HTMLResponse:
    cfg = get_config()
    safe_auth = html.escape(str(cfg.mcp_auth_enabled).lower())
    body = _DASHBOARD_HTML.format(auth_enabled=safe_auth)
    return HTMLResponse(body)


async def api_status(request: Request) -> JSONResponse:
    cfg = get_config()
    return JSONResponse(
        {
            "status": "ok",
            "auth_enabled": cfg.mcp_auth_enabled,
        }
    )


# ---------------------------------------------------------------------------
# Login page & API
# ---------------------------------------------------------------------------

_LOGIN_HTML = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Homebox Login — Get API Token</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 500px; margin: 4rem auto; color: #222; }}
    h1 {{ font-size: 1.4rem; }}
    label {{ display: block; margin-top: 1rem; font-weight: 500; }}
    input {{ width: 100%; padding: 0.5rem; margin-top: 0.25rem; border: 1px solid #d1d5db;
             border-radius: 6px; font-size: 1rem; box-sizing: border-box; }}
    button {{ margin-top: 1.5rem; padding: 0.6rem 1.5rem; background: #2563eb; color: #fff;
              border: none; border-radius: 6px; font-size: 1rem; cursor: pointer; }}
    button:hover {{ background: #1d4ed8; }}
    .result {{ margin-top: 1.5rem; padding: 1rem; border-radius: 6px; }}
    .result.ok {{ background: #f0fdf4; border: 1px solid #86efac; }}
    .result.err {{ background: #fef2f2; border: 1px solid #fca5a5; }}
    .token-box {{ font-family: monospace; font-size: 0.85rem; word-break: break-all;
                  background: #f3f4f6; padding: 0.75rem; border-radius: 4px; margin-top: 0.5rem;
                  user-select: all; cursor: pointer; }}
    .muted {{ color: #666; font-size: 0.85rem; margin-top: 0.5rem; }}
    .back {{ margin-top: 2rem; display: inline-block; color: #2563eb; text-decoration: none; }}
  </style>
</head>
<body>
  <h1>Get Homebox API Token</h1>
  <p>Log in with your Homebox credentials to retrieve a bearer token.</p>

  <p class="muted">Authenticating against: <code>{homebox_url}</code></p>

  <form id="loginForm">
    <label for="username">Username</label>
    <input type="text" id="username" autocomplete="username" required>

    <label for="password">Password</label>
    <input type="password" id="password" autocomplete="current-password" required>

    <button type="submit">Log In &amp; Get Token</button>
  </form>

  <div id="result" style="display:none"></div>
  <a class="back" href="/">&larr; Back to dashboard</a>

  <script>
    document.getElementById('loginForm').addEventListener('submit', async (e) => {{
      e.preventDefault();
      const result = document.getElementById('result');
      result.style.display = 'none';

      const username = document.getElementById('username').value;
      const password = document.getElementById('password').value;

      try {{
        const resp = await fetch('/api/login', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{ username, password }})
        }});
        const data = await resp.json();

        if (resp.ok && data.token) {{
          result.className = 'result ok';
          result.innerHTML = '<strong>Token retrieved successfully!</strong>'
            + '<div class="token-box">' + escapeHtml(data.token) + '</div>'
            + '<p class="muted">Click the token to select it, then copy. '
            + 'Set this as your <code>HOMEBOX_TOKEN</code> environment variable.</p>';
          if (data.saved) {{
            result.innerHTML += '<p class="muted"><strong>Token saved to server config.</strong></p>';
          }}
        }} else {{
          result.className = 'result err';
          result.innerHTML = '<strong>Login failed:</strong> ' + escapeHtml(data.error || 'Unknown error');
        }}
      }} catch (err) {{
        result.className = 'result err';
        result.innerHTML = '<strong>Error:</strong> ' + escapeHtml(err.message);
      }}
      result.style.display = 'block';
    }});

    function escapeHtml(s) {{
      const div = document.createElement('div');
      div.textContent = s;
      return div.innerHTML;
    }}
  </script>
</body>
</html>
"""


async def login_page(request: Request) -> HTMLResponse:
    """Render the login form."""
    cfg = get_config()
    safe_url = html.escape(cfg.homebox_url)
    return HTMLResponse(_LOGIN_HTML.format(homebox_url=safe_url))


_login_attempts: dict[str, list[float]] = {}
_LOGIN_RATE_WINDOW = 60.0  # seconds
_LOGIN_RATE_MAX = 5  # max attempts per window
_LOGIN_MAX_BODY = 4096  # bytes
_LOGIN_MAX_TRACKED_IPS = 1000  # cap to prevent memory exhaustion


async def api_login(request: Request) -> JSONResponse:
    """Authenticate against the configured Homebox instance and return the bearer token.

    Accepts JSON: {"username": "...", "password": "..."}
    Always uses the server's configured HOMEBOX_URL (not user-supplied) to prevent SSRF.
    """
    import time

    # Rate limit by client IP
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()

    # Periodic global eviction: when dict exceeds cap, purge all expired entries
    if len(_login_attempts) > _LOGIN_MAX_TRACKED_IPS:
        stale = [
            ip for ip, ts in _login_attempts.items()
            if not any(now - t < _LOGIN_RATE_WINDOW for t in ts)
        ]
        for ip in stale:
            del _login_attempts[ip]

    attempts = _login_attempts.get(client_ip, [])
    attempts = [t for t in attempts if now - t < _LOGIN_RATE_WINDOW]
    if not attempts:
        _login_attempts.pop(client_ip, None)
    if len(attempts) >= _LOGIN_RATE_MAX:
        return JSONResponse(
            {"error": "Too many login attempts. Try again later."},
            status_code=429,
        )
    attempts.append(now)
    _login_attempts[client_ip] = attempts

    # Limit request body size
    content_length = request.headers.get("content-length")
    try:
        if content_length and int(content_length) > _LOGIN_MAX_BODY:
            return JSONResponse({"error": "Request too large"}, status_code=413)
    except ValueError:
        pass  # Malformed content-length header, let body-size check handle it

    try:
        raw_body = await request.body()
        if len(raw_body) > _LOGIN_MAX_BODY:
            return JSONResponse({"error": "Request too large"}, status_code=413)
        body = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    username = body.get("username", "").strip()
    password = body.get("password", "")
    if not username or not password:
        return JSONResponse(
            {"error": "Username and password are required"}, status_code=400
        )

    cfg = get_config()
    hb_url = cfg.homebox_url
    if not hb_url:
        return JSONResponse(
            {"error": "HOMEBOX_URL is not configured on the server"}, status_code=500
        )

    import httpx

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as hc:
            resp = await hc.post(
                f"{hb_url}/api/v1/users/login",
                json={"username": username, "password": password},
            )
            if resp.status_code == 401:
                return JSONResponse(
                    {"error": "Invalid username or password"}, status_code=401
                )
            resp.raise_for_status()
            data = resp.json()
            token = data.get("token", "")
            if not token:
                return JSONResponse(
                    {"error": "Login succeeded but no token in response"},
                    status_code=502,
                )
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "Cannot connect to Homebox server"}, status_code=502
        )
    except httpx.ReadTimeout:
        return JSONResponse(
            {"error": "Homebox server timed out"}, status_code=504
        )
    except httpx.HTTPStatusError as exc:
        return JSONResponse(
            {"error": f"Homebox returned HTTP {exc.response.status_code}"},
            status_code=502,
        )

    # Also update the running client's token so tools work immediately
    await client.set_token(token)
    logger.info("Login token retrieved and applied to running client")

    return JSONResponse({"token": token, "saved": True})


# ---------------------------------------------------------------------------
# Application assembly
# ---------------------------------------------------------------------------


async def shutdown() -> None:
    """Clean up the Homebox client on server shutdown."""
    await client.close()


def create_app() -> Starlette:
    """Build the Starlette app with MCP mounted at root."""
    mcp_app = mcp.http_app(transport="sse")

    routes = [
        Route("/", dashboard),
        Route("/api/status", api_status),
        Route("/login", login_page),
        Route("/api/login", api_login, methods=["POST"]),
        Mount("/", app=mcp_app),
    ]

    # Propagate FastMCP's lifespan to the parent app so its internal
    # session/task groups are properly initialized (required since FastMCP 3.x).
    app = Starlette(
        routes=routes,
        middleware=[Middleware(BearerAuthMiddleware)],
        lifespan=getattr(mcp_app, "lifespan", None),
        on_shutdown=[shutdown],
    )
    return app


app = create_app()

if __name__ == "__main__":
    cfg = get_config()
    logger.info(
        "Starting Homebox MCP on %s:%s", cfg.server_host, cfg.server_port
    )
    uvicorn.run(
        "server:app",
        host=cfg.server_host,
        port=cfg.server_port,
        log_level=cfg.log_level,
    )

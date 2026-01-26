# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-26

### Added

- **New tool**: `homebox_get_location_tree` - Returns complete location hierarchy tree
  - Addresses [Issue #1](https://github.com/oangelo/homebox-mcp/issues/1)
  - Fetches all locations with parent/children relationships
  - Returns nested tree structure for easy hierarchy visualization
- All tool docstrings translated to English

### Changed

- **Internationalization**: Project translated to English
- Dashboard UI now in English
- Documentation in English with Portuguese version available
- Added `README-pt-br.md` and `DOCS-pt-br.md` for Portuguese speakers
- `homebox_list_locations` now documents Homebox API limitation (parent_id always null)

### Fixed

- Documented workaround for Homebox API not returning parent_id in list endpoint

## [0.1.8] - 2026-01-10

### Added

- Support for Basic Authentication (client_id:client_secret)
- Debug logging for Authorization headers
- Better error messages for authentication

### Changed

- Claude.ai now uses OAuth Client ID + Client Secret fields
- Client ID can be any text (e.g., "mcp")
- Client Secret should contain the authentication token

## [0.4.0] - 2026-01-09

### Added

- **Optional OAuth authentication** for the MCP endpoint
- New `mcp_auth_enabled` option to enable/disable authentication
- New `mcp_auth_token` option to set the Bearer token
- Dashboard shows authentication status
- Recommendation: test without auth first, then enable

### How to Use

1. Test the connection with `mcp_auth_enabled: false`
2. After it works, set a token in `mcp_auth_token`
3. Enable `mcp_auth_enabled: true`
4. In Claude.ai, configure: OAuth Client ID = `mcp`, OAuth Client Secret = your token

## [0.3.0] - 2026-01-09

### Changed

- **BREAKING**: Removed email/password authentication (didn't work correctly)
- Now uses only API Token authentication
- Simplified configuration: only `homebox_url`, `homebox_token`, and `log_level`

### How to Migrate

1. In Homebox, go to **Profile** → **API Tokens** → **Create Token**
2. Copy the generated token
3. Configure the addon with the token

## [0.2.2] - 2026-01-09

### Changed

- Dashboard now shows clear instructions for Cloudflare Tunnel configuration
- Internal address (`http://homeassistant:8099`) displayed for tunnel configuration
- Instructions on adding `/sse` to the tunnel address for Claude.ai

### Fixed

- FastMCP API fix: `sse_app()` → `http_app(transport="sse")`

## [0.2.0] - 2026-01-06

### Added

- Web status dashboard on the addon homepage
- Displays connection status with Homebox
- Shows count of locations, items, and labels
- Displays server uptime
- Shows MCP endpoint for easy configuration
- List of available tools in the dashboard
- API endpoint `/api/status` for programmatic queries
- Auto-refresh every 30 seconds

## [0.1.1] - 2026-01-06

### Added

- Port 8099 exposed directly for easier external connection
- Support for direct connection via `http://YOUR_IP:8099/sse`

### Fixed

- Removed deprecated `description` parameter from FastMCP
- Removed Alpine package version pinning

## [0.1.0] - 2026-01-06

### Added

- Initial MCP server with SSE support
- Integration with Homebox API v1
- Tools for location management:
  - `homebox_list_locations`
  - `homebox_get_location`
  - `homebox_create_location`
  - `homebox_update_location`
  - `homebox_delete_location`
- Tools for item management:
  - `homebox_list_items`
  - `homebox_get_item`
  - `homebox_search`
  - `homebox_create_item`
  - `homebox_update_item`
  - `homebox_move_item`
  - `homebox_delete_item`
- Tools for label management:
  - `homebox_list_labels`
  - `homebox_create_label`
  - `homebox_update_label`
  - `homebox_delete_label`
- Statistics tool:
  - `homebox_get_statistics`
- Automatic authentication with token renewal
- Configuration via Home Assistant addon options
- Supported architectures: amd64, aarch64

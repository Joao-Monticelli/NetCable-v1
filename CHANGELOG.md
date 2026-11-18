# Changelog

All notable changes to NetCable. Versions follow [semantic versioning](https://semver.org/).

## [1.0.0] — 2026-11

First stable release: one Docker image, first-run setup, automatic backups, smart alerts, network discovery and SNMP metrics.

### Added
- **Single Docker image** `ghcr.io/joao-monticelli/netcable` (UI + API on port 8080) for amd64 and arm64.
- **First-run setup**: the first visit creates the admin account; no default passwords.
- **Automatic secret key** stored in `data/secret.key` (secrets encrypted with the old development key are re-encrypted).
- **Daily backups**: `.zip` with the database, every map (JSON) and the device model catalog; configurable folder, time and retention; *Back up now* and download in the UI.
- **Map export/import v2**: includes the device models used, uplinks and map shortcuts; import always creates a new project and accepts old JSON exports and backup `.zip` files.
- Versioned **database migrations** with an automatic copy of the database before upgrading.
- App version shown on the login screen and in `/api/health`.
- Racks with realistic front panels, device model library and port-to-port cables.
- Team roles (Admin, Editor, Viewer), SMTP email alerts and daily report, latency chart.
- English UI by default with Portuguese option (also for emails and API errors).
- Toolbar: hide port-to-port cables, device search (`Ctrl+K`) and hover highlighting.
- **Smart alerts by dependency:** each device can have an uplink ("depends on"), set by hand or computed from the cables starting at a root device. When the uplink is down, devices behind it show as *unreachable* (amber), send no alert of their own and are listed in the uplink's alert; recovery is grouped the same way.
- **Maintenance windows** for a whole map (toolbar 🔧) or a single device (1–24 h, up to 30 days via API). Alerts are muted; monitoring and history continue. Shown on the map, in the editor and on the public/TV page.
- **Alert channels in the UI** (⚙️ → Alert channels): Discord, ntfy, Telegram and JSON webhook, with test buttons; secrets stored encrypted and never echoed in error messages. Env vars `DISCORD_WEBHOOK_URL`, `NTFY_URL`, `NTFY_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ALERT_WEBHOOK_URL`.
- **Network discovery:** scan a private range (CIDR, start-end or single IP, up to 1024 addresses) from the editor; results show reverse-DNS name, open ports, suggested type and whether the IP is already on a map; add the selected ones in one click.
- New device types: Access Point, Printer and Camera.
- **SNMP metrics** for SNMPv3 devices: CPU, memory, temperature, uptime and per-port link/speed/traffic/errors (standard MIBs plus Cisco, MikroTik, UCD/lm-sensors), stored as history. Shown on the map, as real port LEDs in racks and in a metrics window with charts and a port table. Optional SNMPv3 context.
- **Temperature/CPU alerts** with configurable limits (3 readings above to alert, hysteresis to recover), respecting maintenance windows.
- **Shortcuts between maps** ("Shortcut to another map" type): live online/offline summary of the target map, red when something is down there, double-click to open.
- End-to-end QA robot (`qa/`) and real SNMPv3 integration tests (snmpsim), both running in CI.

### Changed
- Monitoring runs on the server (TCP + ICMP in parallel, or SNMPv3) instead of in each browser.
- Public links use a random, revocable token.
- Repository docs, compose files and CI comments are now in English (Portuguese README kept as `README.pt-BR.md`); example `TZ` defaults to `Etc/UTC`.

### Deprecated
- The separate `netcable-backend` and `netcable-frontend` images are still published for now, but new installs should use the single image.

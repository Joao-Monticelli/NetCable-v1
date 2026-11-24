# Changelog

All notable changes to NetCable. Versions follow [semantic versioning](https://semver.org/).

## [Unreleased]

### Added
- **HTTP(S) monitor**: new monitoring method for websites, APIs and web panels — URL, expected status code, text that must be on the page and optional certificate verification (for self-signed devices).
- **TLS certificate expiry alerts**: warning N days before the certificate expires (default 14), when it is already expired and when it is renewed; days left shown on the map. Works with self-signed certificates.
- **SLA report (CSV)** for 7, 30 or 90 days: availability, downtime, outages and average latency per device (History → Availability → Export SLA).
- **Audit log** (⚙️ → Audit log, admins): logins (successful, failed, blocked), user changes, maps, public links, maintenance, settings and backups, with user, time and IP. Kept for `AUDIT_RETENTION_DAYS` (default 365).
- **Prometheus endpoint** `/metrics` (enabled with `METRICS_TOKEN` or `METRICS_PUBLIC=true`): device up/unreachable/maintenance, latency, SNMP CPU/memory/temperature, HTTP status and certificate days.
- **Secret key rotation** command `python -m app.rotacao_chave`: re-encrypts every stored secret with a new key, keeping copies of the database and the old key.

### Security
- A development `backend/data/` folder (database, `secret.key`, backups) was committed to the repository by mistake and is no longer tracked. Docker installs are not affected (they create their own key in their data volume); anyone who ran NetCable straight from a repository checkout using that folder should rotate the key and change the stored passwords and tokens.
- Login tokens are now signed with **PyJWT** instead of `python-jose`, which (with its `ecdsa` dependency) has known vulnerabilities and no fixed release. Existing sessions stay valid.
- **pysnmp 7** replaces pysnmp 4.4, so `pyasn1` can be updated past several known vulnerabilities in the decoding of SNMP responses. `pip-audit` reports no known vulnerabilities in the backend dependencies.

### Changed
- The monitor and SNMP metrics thread pools now live for the whole process, so SNMP engines are reused between cycles instead of being recreated every cycle.
- `python -m app.rotacao_chave` exits with a clear message instead of a traceback when there is no terminal to confirm (use `--sim`).
- Unverified HTTPS checks (certificate verification turned off for a device) no longer write a warning to the log on every check.
- CI uses snmpsim 1.x for the SNMPv3 integration tests.

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
- Network discovery suggests the type from the device name too (`printer`, `cam`, `sw-`, `ap-`, `nas`, `pfsense`…); phones, VoIP, IoT and devices without evidence are suggested as the new **Other** type instead of *Server*.
- `PORT` variable: the port NetCable listens on inside the container, so it can run with `network_mode: host` (needed to show MAC addresses in discovery). The discovery window explains this when no MAC is visible.
- Build artifacts, `node_modules`, Python caches and local data are no longer tracked in the repository.
- Monitoring runs on the server (TCP + ICMP in parallel, or SNMPv3) instead of in each browser.
- Public links use a random, revocable token.
- Repository docs, compose files and CI comments are now in English (Portuguese README kept as `README.pt-BR.md`); example `TZ` defaults to `Etc/UTC`.

### Deprecated
- The separate `netcable-backend` and `netcable-frontend` images are still published for now, but new installs should use the single image.

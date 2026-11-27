# Changelog

All notable changes to NetCable. Versions follow [semantic versioning](https://semver.org/).

## [Unreleased]

## [1.1.0] — 2026-11-27

### Added
- **Incidents on the public status page**: post what is going on (title, impact, affected services, message) and follow-up updates
  (Investigating → Identified → Monitoring → Resolved); the page shows the timeline and keeps resolved incidents for 7 days.
- **Alert escalation**: when a device stays offline for 15 min to 8 h and nobody acknowledges it, one "escalated" alert goes to other
  people (e-mail addresses, a Telegram chat and/or an ntfy topic). Off by default (⚙️ → Alert channels).
- **Cables from LLDP/CDP**: ⚙️ → Discover cables asks the SNMPv3 devices of a map for their LLDP/CDP neighbors, suggests the cables
  between devices of the map (port to port when the ports are drawn) and lists neighbors that are not on the map yet.
- **Login with LDAP / Active Directory** (⚙️ → Directory): accounts created at the first login, role from directory groups at every
  login, test button, LDAPS/STARTTLS; local accounts keep working when the directory is down.
- **Two-factor authentication (TOTP)**: optional per user (My profile), QR code for any authenticator app, 10 single-use recovery codes, admin reset in ⚙️ → Users and `python -m app.redefinir_2fa <user>` for a locked-out admin. Wrong codes share the login lockout.
- **Acknowledge alerts** ("I'm on it"): on an offline device, with an optional note; the channels are told who is handling it, the map shows it, and it clears when the device is back.
- **Reminders** for devices still offline and not acknowledged (every 15 min to 4 h, off by default; ⚙️ → Alert channels).
- **Scheduled and weekly maintenance windows** (🔧 → Schedule / calendar): for later, or every week at a time in the system time zone; ending maintenance during a weekly window skips only that occurrence.
- **Public status page** per map (`/status/<token>`, separate from the map link): status and 90-day daily availability of the devices you choose, maintenance in progress or coming up; no IPs or layout; cached for 30 s.
- **HTTP(S) monitor**: new monitoring method for websites, APIs and web panels — URL, expected status code, text that must be on the page and optional certificate verification (for self-signed devices).
- **TLS certificate expiry alerts**: warning N days before the certificate expires (default 14), when it is already expired and when it is renewed; days left shown on the map. Works with self-signed certificates.
- **SLA report (CSV)** for 7, 30 or 90 days: availability, downtime, outages and average latency per device (History → Availability → Export SLA).
- **Audit log** (⚙️ → Audit log, admins): logins (successful, failed, blocked), user changes, maps, public links, maintenance, settings and backups, with user, time and IP. Kept for `AUDIT_RETENTION_DAYS` (default 365).
- **Prometheus endpoint** `/metrics` (enabled with `METRICS_TOKEN` or `METRICS_PUBLIC=true`): device up/unreachable/maintenance, latency, SNMP CPU/memory/temperature, HTTP status and certificate days.
- **Secret key rotation** command `python -m app.rotacao_chave`: re-encrypts every stored secret with a new key, keeping copies of the database and the old key.

### Security
- New backend dependency `ldap3` (directory login).
- A development `backend/data/` folder (database, `secret.key`, backups) was committed to the repository by mistake and is no longer tracked. Docker installs are not affected (they create their own key in their data volume); anyone who ran NetCable straight from a repository checkout using that folder should rotate the key and change the stored passwords and tokens.
- Login tokens are now signed with **PyJWT** instead of `python-jose`, which (with its `ecdsa` dependency) has known vulnerabilities and no fixed release. Existing sessions stay valid.
- **pysnmp 7** replaces pysnmp 4.4, so `pyasn1` can be updated past several known vulnerabilities in the decoding of SNMP responses. `pip-audit` reports no known vulnerabilities in the backend dependencies.

### Changed
- The API code (`backend/app/main.py`, 2,200 lines) is split by subject into `app/rotas/` (contas, configuracoes, mapas, rede, prometheus), `app/nucleo.py` and `app/monitoramento.py`; no endpoint changed.
- Deprecated APIs replaced (`datetime.utcnow`, Pydantic `class Config`/`.dict()`, FastAPI `on_event`, SQLAlchemy `declarative_base` import): test warnings went from 256 to 2.
- The web UI loads its pages on demand: the first download goes from 690 kB to 265 kB, and the public status page does not load the map editor.
- The monitor and SNMP metrics thread pools now live for the whole process, so SNMP engines are reused between cycles instead of being recreated every cycle.
- `python -m app.rotacao_chave` exits with a clear message instead of a traceback when there is no terminal to confirm (use `--sim`).
- Unverified HTTPS checks (certificate verification turned off for a device) no longer write a warning to the log on every check.
- CI uses snmpsim 1.x for the SNMPv3 integration tests (fixed a missing space in the simulator command of the test job).
- LLDP/CDP neighbor discovery reads local port names, management addresses and MAC-style port ids correctly.
- The QA robot covers 2FA, acknowledgements, the maintenance calendar, the status page with incidents, escalation, LDAP and LLDP cables.

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

# NetCable — self-hosted network map & monitoring

![Status](https://img.shields.io/badge/status-beta-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-amd64%20%7C%20arm64-2496ED)
![CI](https://github.com/Joao-Monticelli/NetCable-v1/actions/workflows/docker-build.yml/badge.svg)

**English** · [Português](README.pt-BR.md)

<img width="1920" alt="NetCable" src="https://github.com/user-attachments/assets/91e328d3-c12c-4d81-887d-38ea06ef9e4c" />

NetCable is an open-source, self-hosted tool to **draw your network and keep an eye on it**.
Drag devices onto a canvas, mount them in racks that look like the real thing, cable port to
port, and NetCable pings everything in the background and tells you (email, Telegram, webhook)
when something goes down.

It runs as **one Docker container** on anything: a mini PC, a VM, a NAS, a Raspberry Pi.

> ⚠️ Beta: under active development. Feedback and issues are very welcome.

## Features

- 📡 **Network discovery** — scan a range (e.g. `192.168.1.0/24`), see who answered with hostname, open ports and a suggested type, and add them to the map in one click.
- 🗺️ **Visual map** — drag & drop devices, draw cables, labels, search (`Ctrl+K`) and hover highlighting.
- 🧭 **Shortcuts between maps** — build an overview map (HQ → branches → datacenter); each shortcut shows the live online/offline count of its map, turns red when something is down there and opens it on double-click.
- 🗄️ **Realistic racks** — 4U to 48U racks; switches, servers, NAS, patch panels, UPS… snap to U positions.
- 🧩 **Device model library** — register your real gear (e.g. “4× RJ45 + 2× SFP, 1U”) and its front panel is drawn with exactly those ports.
- 🔌 **Port-to-port cables** — connect switch port 12 to firewall eth3; ports show as in use with tooltips.
- 📡 **Server-side monitoring** — TCP (80/443/22) + ICMP in parallel, SNMPv3, or HTTP(S); works with no browser open.
- 🔒 **HTTP(S) & certificate monitor** — check a website, API or web panel (status code, response time, text on the page) and get an alert before its TLS certificate expires.
- 🚨 **Alerts** — email, Discord, ntfy, Telegram and webhook on down/up, grouped per cycle, per-device on/off.
- 🧠 **Smart alerts** — set each device's uplink (or compute them from the cables): when a switch dies you get **one** alert listing what is behind it, and those devices turn amber (*unreachable*) on the map. **Maintenance windows** mute a device or a whole map now, at a scheduled time or every week.
- 👀 **Acknowledge alerts** — click *I'm on it* on a device that is down: the team is told who is handling it, and optional reminders ("still offline after 1 h") stop.
- 🌡️ **SNMP metrics** — CPU, memory, temperature, uptime and per-port link/traffic for SNMPv3 devices, with charts, real port LEDs on the rack and temperature/CPU alerts.
- 📊 **Uptime & latency** — availability %, outages, latency chart (24 h / 7 d / 30 d), a daily email report and an **SLA report in CSV** (7 / 30 / 90 days).
- 📈 **Prometheus `/metrics`** — device status, latency, SNMP metrics and certificate expiry for Grafana.
- 🕵️ **Audit log** — who logged in, changed users, saved or deleted maps, shared links or changed settings, and when.
- 👥 **Team roles** — Admin, Editor and Viewer (great for a NOC TV).
- 🔐 **Two-factor authentication** — optional 6-digit codes from an authenticator app, with single-use recovery codes.
- 📺 **Public link & TV mode** — read-only, auto-refreshing, full screen, revocable secret link.
- 🟢 **Public status page** — a simple page for customers or the team: each service's status and 90-day availability bars, plus scheduled maintenance. No IPs or network layout.
- 💾 **Backups** — daily `.zip` (all maps + model catalog + full database) to a folder you choose; export/import single maps as JSON.
- 🌐 **English / Português** — per user; also applies to emails and API errors.

## Quick start (Docker)

```yaml
# docker-compose.yml
services:
  netcable:
    image: ghcr.io/joao-monticelli/netcable:latest
    container_name: netcable
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data      # database, secret key and backups
    environment:
      - TZ=America/New_York
```

```bash
docker compose up -d
```

Open `http://SERVER-IP:8080`. On the first visit NetCable asks you to **create the admin account** —
there are no default passwords. A secret key is generated automatically in the data folder.

Or with plain Docker:

```bash
docker run -d --name netcable -p 8080:8080 -v netcable-data:/app/data --restart unless-stopped ghcr.io/joao-monticelli/netcable:latest
```

Images are published for **amd64** and **arm64** (Raspberry Pi 4/5). Pin a version with
`ghcr.io/joao-monticelli/netcable:1.0.0` if you prefer controlled upgrades.

### TrueNAS SCALE

Apps → Discover Apps → Custom App → *Install via YAML* and paste [`install/trueNAS.yml`](install/trueNAS.yml)
(change the pool path). Details in [INSTALL.md](INSTALL.md).

## Configuration

Everything is optional. Email (SMTP), users, backups and languages are configured in the web UI (⚙️ menu).

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/Sao_Paulo` | Default time zone for reports and backups |
| `MONITOR_INTERVAL` | `15` | Seconds between monitoring cycles (`0` disables) |
| `MONITOR_FAILURE_THRESHOLD` | `2` | Consecutive failures before a device is marked offline |
| `HISTORY_RETENTION_DAYS` | `30` | Days of history kept (`0` = forever) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | — | Telegram alerts (also configurable in ⚙️ → Alert channels) |
| `DISCORD_WEBHOOK_URL` | — | Discord channel webhook |
| `NTFY_URL` / `NTFY_TOKEN` | — | ntfy topic (e.g. `https://ntfy.sh/my-secret-topic`) and optional token |
| `ALERT_WEBHOOK_URL` | — | Receives a JSON POST on down/up |
| `ALERT_LANGUAGE` | `en` | Language of the channel messages (`en` or `pt`) |

Values set in the UI take precedence over the environment variables.
| `ADMIN_USER` / `ADMIN_PASSWORD` | — | Create or recover an admin from the environment (instead of the first-run screen) |
| `SECRET_KEY` | auto | Overrides the key stored in `data/secret.key` |
| `SNMP_METRICS_INTERVAL` | `60` | Seconds between SNMP metric collections (`0` disables) |
| `PORT` | `8080` | Port NetCable listens on inside the container; only useful with `network_mode: host` |
| `DISCOVERY_ALLOW_PUBLIC` | — | `1` allows network discovery on public IP ranges |
| `DISCOVERY_TIMEOUT` / `DISCOVERY_WORKERS` | `0.8` / `128` | Per-probe timeout (s) and parallel probes during discovery |
| `METRICS_TOKEN` | — | Enables `/metrics` for Prometheus, protected by this Bearer token |
| `METRICS_PUBLIC` | — | `true` enables `/metrics` without a token (only on a trusted network) |
| `AUDIT_RETENTION_DAYS` | `365` | Days the audit log is kept (`0` = forever) |

## Large networks: shortcuts between maps

Split a big network into several maps (one per site, floor or rack room) and create an **overview map** with shortcuts:
**Add → type "Shortcut to another map"**, pick the target map. The shortcut shows how many devices are online/offline over there,
turns red when anything is down, and **double-click** (or a single click in view mode) opens that map. Shortcuts can be cabled
like any device (e.g. the WAN link between two sites) and are kept in backups/exports (re-linked by map name on import).

## Network discovery

Click the 📡 radar button in the editor toolbar, enter a range (`192.168.1.0/24`, `10.0.0.10-10.0.0.60` or a single IP) and **Scan**.
The NetCable server pings every address and checks common ports (SSH, HTTP/S, SMB, RDP, DNS, printers, cameras, Proxmox, Synology),
then lists what answered with its reverse-DNS name and a suggested type (from the open ports and hints in the name, such as
`printer`, `cam`, `sw-`, `ap-`, `nas`; phones, VoIP and IoT devices, or anything without evidence, are suggested as **Other**). Devices already on a map are flagged and unchecked.
Pick what you want, adjust names/types and click **Add to the map**, then save.

- Only private ranges (10/8, 172.16/12, 192.168/16, 100.64/10) of up to 1024 addresses are allowed. Set `DISCOVERY_ALLOW_PUBLIC=1` to scan public ranges in a lab.
- In Docker the default bridge network can reach your LAN, so scanning works. **MAC addresses** are only shown with host networking,
  because in bridge mode the container cannot see your LAN's ARP table. To enable it, replace `ports:` with `network_mode: host`
  and, if port 8080 is already taken on the host, set `PORT` (e.g. `PORT=3080` on TrueNAS):

  ```yaml
  services:
    netcable:
      image: ghcr.io/joao-monticelli/netcable:latest
      network_mode: host        # instead of ports:
      environment:
        - PORT=3080             # NetCable listens here: http://SERVER-IP:3080
  ```
- Editors and admins can scan; viewers cannot.

## SNMP metrics

For devices monitored with **SNMPv3**, NetCable collects every minute (`SNMP_METRICS_INTERVAL`):

| Metric | Sources (first that answers) |
|---|---|
| CPU | HOST-RESOURCES `hrProcessorLoad`, Cisco `cpmCPUTotal5minRev`, UCD `ssCpuIdle` (Linux/NAS) |
| Memory | HOST-RESOURCES `hrStorageRam`, UCD `memTotalReal/memAvailReal`, Cisco memory pools |
| Temperature | ENTITY-SENSOR (°C sensors), LM-SENSORS, MikroTik, Cisco `ciscoEnvMonTemperature` (highest sensor) |
| Ports | IF-MIB: name, description (alias), link status, speed, traffic (64-bit counters) and errors |

- On the map: temperature and CPU next to the device; in racks, **port N lights up with the real link of the N-th physical interface** (RJ45 first, then SFP) and the tooltip shows name, description, speed and traffic.
- Click **View metrics** in the device (or click the device in view mode) for charts (1 h / 24 h / 7 days, also as a table) and the port table.
- **Alerts:** ⚙️ → Alert channels → *Temperature and CPU limits* (default 75 °C and 95%; `0` disables). An alert fires after 3 readings in a row above the limit and again when it returns to normal. Maintenance windows mute them too.
- SNMPv3 **context** is optional (some devices use one per VRF/instance).
- Tested against a simulated SNMPv3 agent ([snmpsim](https://github.com/etingof/snmpsim)) in CI; please open an issue with your device model if a metric shows "—".

## Smart alerts

- **Uplink (depends on):** open a device and pick the device it depends on (e.g. the switch it is plugged into).
  Faster: open your gateway/firewall and click **Use as root and compute uplinks from cables** — NetCable walks the cables and fills in every uplink. Save the map.
- When an uplink goes down, devices behind it are shown in **amber (unreachable)**, don't send their own alert and are listed in the uplink's alert
  (*"Core switch OFFLINE — 12 devices behind it unreachable: …"*). When it comes back, one recovery alert lists them too.
- **Maintenance:** 🔧 in the toolbar mutes the whole map for 1–24 h; inside a device you can mute just that device.
  Monitoring and history keep running; devices that went down during maintenance don't send a "back online" alert afterwards.
- **Maintenance calendar:** 🔧 → **Schedule / calendar…** plans a window for later (e.g. Saturday 22:00 → 02:00) or **every week**
  (e.g. every Sunday at 02:00 for 2 h, in the system time zone), for the whole map or one device. *End maintenance* during a weekly
  window skips only that occurrence.
- **Acknowledge (*I'm on it*):** open a device that is offline and click **I'm on it** (optionally with a note). The channels get
  *"👀 ana acknowledged the alert and is on it"*, the map shows 👁 on the device, and the acknowledgement goes away by itself when
  the device comes back (the recovery alert says who was on it).
- **Reminders:** ⚙️ → **Alert channels** → *Reminder for devices that stay offline* repeats the alert every 15 min … 4 h while a
  device is still down and nobody acknowledged it (off by default). Maintenance and the uplink rules apply to reminders too.
- **Channels:** ⚙️ → **Alert channels** (admins) for Discord, ntfy (push notifications on your phone), Telegram and a generic JSON webhook, each with a *Test* button. Tokens and URLs are stored encrypted.

## HTTP(S) and certificate monitoring

Pick **HTTP(S): website, API or web panel** as the monitoring method of a device:

- **URL** — e.g. `https://intranet.local/health`. Empty means `http://<device IP>/`.
- **Expected status** — empty accepts any 2xx/3xx; set `200`, `401`… to require one code.
- **Text on page** — optional; the device is offline when the text is missing (catches "200 OK" error pages).
- **Verify the certificate** — turn off for devices with self-signed certificates (printers, NAS, firewalls).
- **Certificate warning** — alert when the certificate expires in N days or less (default 14, `0` turns it off).
  The certificate is read even when it is self-signed, so you also get warned about internal devices.
  One alert is sent when it gets close (or expires) and another when it is renewed; maintenance windows mute it.

The map shows the days left (🔒 `12d`, amber at 14 days or less, red when expired) and the HTTP error when the check fails.

## SLA report, audit log and Prometheus

- **SLA report:** ⚙️ → **History** → *Availability* → **Export SLA (CSV)** for 7, 30 or 90 days: availability %, downtime
  (`h:mm:ss` and seconds), outages and average latency of every device. Opens directly in Excel/LibreOffice.
  The period is limited by `HISTORY_RETENTION_DAYS` (default 30): raise it if you need 90-day reports.
- **Audit log:** ⚙️ → **Audit log** (admins): logins (including failed and blocked ones), users created/changed/deleted,
  maps created/renamed/saved/deleted/imported, public links, maintenance, settings and backups, with user, time and IP.
  Passwords and secrets are never logged.
- **Prometheus:** set `METRICS_TOKEN` and scrape `/metrics`:

  ```yaml
  scrape_configs:
    - job_name: netcable
      metrics_path: /metrics
      authorization: { credentials: "your-metrics-token" }
      static_configs: [{ targets: ["netcable:8080"] }]
  ```

  Series: `netcable_device_up`, `netcable_device_unreachable`, `netcable_device_maintenance`, `netcable_device_latency_ms`,
  `netcable_device_cpu_percent`, `netcable_device_memory_percent`, `netcable_device_temperature_celsius`,
  `netcable_http_status_code`, `netcable_tls_cert_expiry_days` (labels `map`, `device`, `ip`, `type`, `mode`) and
  `netcable_monitor_*`.

## Two-factor authentication

Each user can turn it on in **My profile** → *Two-factor authentication*: scan the QR code with any authenticator app
(Google Authenticator, Microsoft Authenticator, Authy, 1Password…), type the 6-digit code and keep the 10 recovery codes shown.
From then on, logging in asks for the code after the password. Wrong codes count towards the same lockout as wrong passwords.

- Lost the phone? Log in with a recovery code (each works once) and generate new ones in the profile.
- An admin can remove someone's 2FA in ⚙️ → **Users** (the shield button). If the only admin is locked out:
  `docker compose exec netcable python -m app.redefinir_2fa <username>`.
- The secret is stored encrypted with the secret key (and re-encrypted by the key rotation command).

## Public status page

⚙️ → **Public status page** → *Turn on* gives the map an address like `http://server:8080/status/<token>`, separate from the
public map link. It shows, for each device marked **Show on the status page** (on by default), its name, current status
(operational / down / under maintenance) and one bar per day with its availability over the last 90 days, plus maintenance in
progress or scheduled for the next 14 days (with its reason). It shows **no IPs, ids or network layout**, refreshes every minute
and can be given a new address or turned off at any time. Days older than `HISTORY_RETENTION_DAYS` show as *no data*.

## Rotating the secret key

`data/secret.key` encrypts the stored secrets (SMTP/SNMP passwords, alert channels, HTTP monitor URLs) and signs logins.
If it may have leaked, rotate it:

```bash
docker compose stop netcable
docker compose run --rm netcable python -m app.rotacao_chave
docker compose start netcable
```

Every secret is re-encrypted with a new key in one transaction; a copy of the database and of the old key is kept in
`data/backups/` (the old key is only needed to restore older backups). Everybody has to log in again.
If you set `SECRET_KEY` yourself, run it with `--nova-chave "<new value>"` and then update the variable.
If the database leaked too, also change the passwords and tokens stored in NetCable: rotating the key does not make
already leaked secrets safe again.

## Backups & restore

- ⚙️ → **Backup** (admins): daily time, how many files to keep, destination folder and a *Back up now* button.
  In Docker the folder must be inside a mounted volume (default `/app/data/backups`; mount another volume to send them to your NAS).
- Each `.zip` contains `netcable.db` (everything: users, history, settings), one JSON per map and the model catalog.
- **Restore maps:** on the projects screen click **Import** and choose the `.zip` (or a single map `.json`). Imports always create new projects; nothing is overwritten.
- **Restore everything:** stop the container and replace `data/netcable.db` with the one inside the `.zip`.

The database is also copied automatically to `data/backups/` before any schema upgrade.

## Upgrading

```bash
docker compose pull && docker compose up -d
```

Database migrations run automatically. Upgrading from the old two-container setup
(`netcable-backend` + `netcable-frontend`)? Point the compose file to the single image above and keep
the same data folder mounted at `/app/data`.

## Development

```bash
# API (http://localhost:8000)
cd backend && python -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/uvicorn app.main:app --reload

# UI (http://localhost:5173, proxies /api to :8000)
cd frontend && npm install && npm run dev

# Tests
cd backend && venv/bin/pytest -q
cd qa && npm install && npm run qa      # end-to-end robot, report in qa/relatorios/
```

Stack: React 18, Vite, React Flow · FastAPI, SQLAlchemy, SQLite · Docker, GitHub Actions.

### Project layout

| Path | What lives there |
|---|---|
| `backend/app/main.py` | FastAPI app: REST API, auth, background monitoring loop, serves the built UI |
| `backend/app/models.py`, `schemas.py`, `crud.py`, `database.py`, `migracoes.py` | Database models, API schemas, queries and automatic migrations (SQLite) |
| `backend/app/ping_service.py`, `snmp_service.py`, `metricas_snmp.py` | Reachability checks, SNMP queries and SNMP metrics collection |
| `backend/app/alerts.py`, `regras_alerta.py`, `email_service.py` | Alert channels (Telegram, Discord, ntfy, webhook, email) and smart alert rules |
| `backend/app/descoberta.py`, `backup.py`, `i18n.py` | Network discovery, backups/restore, server-side translations |
| `backend/tests/` | pytest suite (plus an SNMPv3 simulator used in CI) |
| `frontend/src/pages/` | Screens: login, projects, map editor, public shared view |
| `frontend/src/components/` | Network map (React Flow), racks, charts, sidebar and all modals |
| `frontend/src/i18n/` | UI translations (English and Portuguese) |
| `qa/` | End-to-end QA robot ([qa/README.md](qa/README.md)) |
| `install/` | Ready-made compose file for TrueNAS SCALE |

## Contributing

Issues and pull requests are welcome — bug reports with screenshots help a lot.
See the [CHANGELOG](CHANGELOG.md) for what changed in each version.

## License

MIT

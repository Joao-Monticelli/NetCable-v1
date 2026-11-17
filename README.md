# NetCable — self-hosted network map & monitoring

![Status](https://img.shields.io/badge/status-beta-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-amd64%20%7C%20arm64-2496ED)
![CI](https://github.com/Joao-Monticelli/NetCable-v1/actions/workflows/docker-build.yml/badge.svg)

**English** · [Português](README.pt-BR.md)

<img width="1080" alt="NetCable map" src="https://github.com/user-attachments/assets/792717d9-2239-4b9a-9959-fdead1927bb7" />

<img width="1678" alt="NetCable racks" src="https://github.com/user-attachments/assets/1267e35c-83bc-4099-a174-ea4889ac81d1" />

NetCable is an open-source, self-hosted tool to **draw your network and keep an eye on it**.
Drag devices onto a canvas, mount them in racks that look like the real thing, cable port to
port, and NetCable pings everything in the background and tells you (email, Telegram, webhook)
when something goes down.

It runs as **one Docker container** on anything: a mini PC, a VM, a NAS, a Raspberry Pi.

> ⚠️ Beta: under active development. Feedback and issues are very welcome.

## Features

- 🗺️ **Visual map** — drag & drop devices, draw cables, labels, search (`Ctrl+K`) and hover highlighting.
- 🗄️ **Realistic racks** — 4U to 48U racks; switches, servers, NAS, patch panels, UPS… snap to U positions.
- 🧩 **Device model library** — register your real gear (e.g. “4× RJ45 + 2× SFP, 1U”) and its front panel is drawn with exactly those ports.
- 🔌 **Port-to-port cables** — connect switch port 12 to firewall eth3; ports show as in use with tooltips.
- 📡 **Server-side monitoring** — TCP (80/443/22) + ICMP in parallel, or SNMPv3; works with no browser open.
- 🚨 **Alerts** — email, Discord, ntfy, Telegram and webhook on down/up, grouped per cycle, per-device on/off.
- 🧠 **Smart alerts** — set each device's uplink (or compute them from the cables): when a switch dies you get **one** alert listing what is behind it, and those devices turn amber (*unreachable*) on the map. **Maintenance windows** mute a device or a whole map for a while.
- 📊 **Uptime & latency** — availability %, outages, latency chart (24 h / 7 d / 30 d) and a daily email report.
- 👥 **Team roles** — Admin, Editor and Viewer (great for a NOC TV).
- 📺 **Public link & TV mode** — read-only, auto-refreshing, full screen, revocable secret link.
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

## Smart alerts

- **Uplink (depends on):** open a device and pick the device it depends on (e.g. the switch it is plugged into).
  Faster: open your gateway/firewall and click **Use as root and compute uplinks from cables** — NetCable walks the cables and fills in every uplink. Save the map.
- When an uplink goes down, devices behind it are shown in **amber (unreachable)**, don't send their own alert and are listed in the uplink's alert
  (*"Core switch OFFLINE — 12 devices behind it unreachable: …"*). When it comes back, one recovery alert lists them too.
- **Maintenance:** 🔧 in the toolbar mutes the whole map for 1–24 h; inside a device you can mute just that device.
  Monitoring and history keep running; devices that went down during maintenance don't send a "back online" alert afterwards.
- **Channels:** ⚙️ → **Alert channels** (admins) for Discord, ntfy (push notifications on your phone), Telegram and a generic JSON webhook, each with a *Test* button. Tokens and URLs are stored encrypted.

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

## Contributing

Issues and pull requests are welcome — bug reports with screenshots help a lot.
See the [CHANGELOG](CHANGELOG.md) for what changed in each version.

## License

MIT

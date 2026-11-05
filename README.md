🌐 NetCable — Visual Network Mapper (BETA)

*Leia em [Português](README.pt-BR.md).*

![Status](https://img.shields.io/badge/Status-BETA-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Python](https://img.shields.io/badge/Python-3.11-yellow)
![React](https://img.shields.io/badge/React-18-blue)

<img width="1080" height="602" alt="image" src="https://github.com/user-attachments/assets/792717d9-2239-4b9a-9959-fdead1927bb7" />

<img width="1678" height="894" alt="netcable2" src="https://github.com/user-attachments/assets/1267e35c-83bc-4099-a174-ea4889ac1d1a" />

<img width="1678" height="894" alt="netcable2" src="https://github.com/user-attachments/assets/8f2d1f5e-7ead-4df1-8c0d-2a4889ac1d1a" />

NetCable is an open-source, self-hosted tool to map and monitor your network in real time. Create visual diagrams by dragging and dropping equipment, connect them with virtual cables, and track the status of every device with real-time alerts.

⚠️ This project is in BETA and under active development. Features may change, bugs may appear, and several improvements are planned (see the Roadmap section). Feedback and contributions are welcome.

✨ Features
🔐 Secure login — JWT authentication

🌐 English by default — one-click PT/EN toggle, persisted per browser

🔍 One-click discovery — ping-sweeps the local subnet, identifies vendors (MAC OUI), guesses device type and OS, and drops everything onto the canvas wired to the gateway

🎨 Visual mapping — create network diagrams by dragging icons and pulling lines (cables)

📡 Smart monitoring — probes each device using TCP (ports 80, 443, 22) and ICMP (ping)

🚨 Real-time alerts — green/red dots, cascade effect (yellow) and audible alarm

🔗 Public link — share the diagram in read-only mode

💾 Export/Import JSON — back up and restore your diagram easily

## 🔧 Recent updates

NetCable received a first evolution in monitoring and integration with real networks:

✅ **Per-device monitoring method** — choose between IP/ICMP + TCP, SNMPv3 or visual-only mode.

✅ **Initial SNMPv3 support** — MD5/SHA authentication, AES/DES privacy, connection test and configurable SNMP port.

✅ **LLDP/CDP neighbor discovery** — reads the neighborhood tables exposed by equipment via SNMP.

✅ **Credential protection** — SNMP settings are encrypted in the backend and passwords are excluded from JSON backups.

✅ **Install diagnostics** — new check of the API, database, SQLite path and PySNMP availability.

✅ **Simplified communication** — the frontend uses the `/api` path, with proxying in Vite and Nginx. Users never configure or even know the backend's internal port.

✅ **Clearer error messages** — connection, API and monitoring failures shown in more detail.

✅ **Compatibility with existing databases** — new monitoring settings are added automatically without wiping current projects.

These features are being validated with real switches, firewalls and other equipment. Automatic node/connection creation from discovery, plus detailed interface, CPU and memory collection, remain planned for upcoming versions.

🚀 How to run (Docker — recommended)
The simplest way to run NetCable is via Docker Compose, on any machine with Docker installed (VPS, mini PC, Raspberry Pi, VM, lab PC, etc.).

bash
git clone https://github.com/Joao-Monticelli/NetCable-v1.git
cd NetCable-v1
# edit docker-compose.yml with user, password and data path
docker compose up -d
Then open http://localhost:<port> in your browser.

💡 NetCable does not require TrueNAS. It runs in any environment with Docker. TrueNAS is just one of the hosting options — see below.

🖥️ Option: install on TrueNAS (Custom App)
If you already use TrueNAS SCALE and want to run NetCable alongside your apps:

Download the YAML install file: install/trueNAS.yml

In TrueNAS, go to Apps → Custom App → Install via YAML

Paste the YAML contents and edit user, password and the pool path

Click Install

For the detailed walkthrough, see INSTALL.md.

⚠️ Note: NetCable is a network app, not a storage app. It runs fine on TrueNAS, but TrueNAS is not required — use the Docker option above if you prefer simplicity.

🏠 Option: install on Raspberry Pi / DietPi (no Docker)
ARM boards (e.g. Raspberry Pi 1) can't run the amd64 container images, so there is a native install: Python backend as a systemd service + prebuilt frontend served by nginx. Files and instructions in `install/dietpi/`.

🛠️ Technologies
Frontend: React, Vite, React Flow, Lucide React, React Hot Toast

Backend: Python, FastAPI, SQLAlchemy, SQLite, Ping3

Infrastructure: Docker, Docker Compose, GitHub Actions, GitHub Container Registry (GHCR)

🗺️ Roadmap
The project is in beta and the following improvements are planned:

□ Multiple users and permissions
□ Device status history (uptime/downtime)
□ External notifications (e-mail, webhook, Telegram/Discord)
□ PostgreSQL as an alternative to SQLite
□ Monitoring performance improvements (queue/scheduling)
□ Automated tests (backend and frontend)
□ API documentation (OpenAPI/Swagger)
□ Light/dark themes
□ ~~Internationalization (pt-BR / en)~~ ✅ done — English default with PT toggle
Suggestions are welcome via Issues.

🤝 Contributing
Contributions are very welcome! Feel free to open Issues with bugs, suggestions or questions, and Pull Requests with improvements. Please write code comments and user-facing strings in English (the UI ships a PT translation via the in-app toggle).

📄 License
This project is under the MIT license. Feel free to use, modify and contribute.

---

*Document maintained by the NetCable team. [Versão em Português](README.pt-BR.md).*

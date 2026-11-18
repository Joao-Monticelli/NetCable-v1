# Installing NetCable on TrueNAS SCALE

NetCable runs as a single container. Data (database, secret key and backups) lives in one folder on your pool.

## 1. Create the data folder

Create a dataset or folder, e.g. `/mnt/tank/apps/netcable`. From the shell:

```bash
mkdir -p /mnt/tank/apps/netcable
```

## 2. Install the app

1. Apps → Discover Apps → **Custom App** → **Install via YAML**.
2. Paste the contents of [`install/trueNAS.yml`](install/trueNAS.yml).
3. Change the volume path `/mnt/YOUR_POOL/apps/netcable` to the folder from step 1 (and `TZ` if needed).
4. Click **Install**.

## 3. First access

Open `http://TRUENAS-IP:3080`. NetCable asks you to create the administrator account on the first visit.

## Backups

⚙️ → **Backup**: by default a `.zip` is written every day to `/app/data/backups` (that is, `backups/` inside the folder from step 1).
To keep backups on another dataset, add a second volume (e.g. `/mnt/tank/backups/netcable:/backups`) and set the folder to `/backups` in the UI.

## Updating

Apps → netcable → **Update** (or pin a version such as `ghcr.io/joao-monticelli/netcable:1.0.0` in the YAML).
Database upgrades run automatically and a copy of the database is saved first.

## Monitoring notes

- Linux servers and switches usually answer TCP/ICMP out of the box.
- Windows may need ICMP (ping) allowed in Windows Firewall.
- Unmanaged switches: add them as "No IP" (visual only).

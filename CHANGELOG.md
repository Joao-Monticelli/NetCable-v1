# Changelog

All notable changes to NetCable. Versions follow [semantic versioning](https://semver.org/).

## [1.0.0] — 2026-11

First stable release: one Docker image, first-run setup and automatic backups.

### Added
- **Single Docker image** `ghcr.io/joao-monticelli/netcable` (UI + API on port 8080) for amd64 and arm64.
- **First-run setup**: the first visit creates the admin account; no default passwords.
- **Automatic secret key** stored in `data/secret.key` (secrets encrypted with the old development key are re-encrypted).
- **Daily backups**: `.zip` with the database, every map (JSON) and the device model catalog; configurable folder, time and retention; *Back up now* and download in the UI.
- **Map export/import v2**: includes the device models used; import always creates a new project and accepts old JSON exports and backup `.zip` files.
- Versioned **database migrations** with an automatic copy of the database before upgrading.
- App version shown on the login screen and in `/api/health`.
- Racks with realistic front panels, device model library and port-to-port cables.
- Team roles (Admin, Editor, Viewer), SMTP email alerts and daily report, latency chart.
- English UI by default with Portuguese option (also for emails and API errors).
- Toolbar: hide port-to-port cables, device search (`Ctrl+K`) and hover highlighting.
- End-to-end QA robot (`qa/`) that runs in CI.

### Changed
- Monitoring runs on the server (TCP + ICMP in parallel, or SNMPv3) instead of in each browser.
- Public links use a random, revocable token.

### Deprecated
- The separate `netcable-backend` and `netcable-frontend` images are still published for now, but new installs should use the single image.

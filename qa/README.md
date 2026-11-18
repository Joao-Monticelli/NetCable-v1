# NetCable QA robot

Uses NetCable like a real user and produces a report — **no AI, no tokens spent**.

```bash
cd qa
npm install          # first time only
npm run qa           # full run (~3 min)
npm run qa:quick     # quick run (~1.5 min, skips the slow public-link scenario)
```

The report is written to `qa/relatorios/<date-time>/relatorio.html` (with screenshots of failures) and `resumo.md`.

## What it does

1. Starts an **isolated** instance: backend with a temporary database (port 8011), frontend (5184) and a fake SMTP server (2526).
   It never touches your database or the NetCable instance you are using.
2. **Scenarios**: login and language, adding a device (including "Test" and response time), racks (mount, move,
   save), models and per-port cables, view mode and public link (TV), users and roles, email,
   history/latency/diagnostics and the unsaved-changes warning.
3. **Free exploration** in English and Portuguese: clicks randomly through screens and modals looking for
   JavaScript exceptions, console errors, HTTP 5xx responses, untranslated text and broken modals.

The process exits with code 1 if it finds problems (useful in CI).

## Optional variables

| Variable | Purpose |
|---|---|
| `QA_BROWSER` | Browser: `msedge` (default on Windows), `chrome`, or empty for Playwright's Chromium (`npx playwright install chromium`) |
| `QA_VER=1` | Opens a visible browser so you can watch the robot |
| `QA_API_PORT`, `QA_WEB_PORT`, `QA_SMTP_PORT` | Change the ports of the test instance |

In Claude Code, the `/qa-diario` command runs the robot and summarizes the report.

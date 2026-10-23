# FocusDesk

A personal, offline-first productivity workspace that combines a **cold email outreach tracker** with a **daily productivity log**, built with Python, NiceGUI and SQLite.

> 🚧 **Work in progress.** The foundation, sender management, outreach entry form and desktop widget are working. The dashboard, tables, calendar and AI features are being built. See the [roadmap](#roadmap).

## Why I built it

I tracked my daily work in an Excel sheet and was about to start cold emailing from 10+ inboxes. A spreadsheet can't warn me when I'm over-sending from one account, remind me to follow up, or show patterns over time. FocusDesk replaces it with one local app where all data stays on my machine.

## Features

### Working now
- **Sender accounts:** manage 10+ inboxes with per-account daily limits, status (active / resting / flagged), warm-up mode and live "sent today" progress bars
- **Add outreach entry:** fast form with a sender dropdown that remembers the last account, a live `X / limit` counter, a usage panel for switching accounts, templates, paste-to-fill, and a collapsible "more details" section
- **Smart warnings:** duplicate recipient, same-domain cooldown, existing company and a Do Not Contact list
- **Desktop widget:** a small always-on-top window with a start/stop stopwatch (Working, Gaming, Rest, Other) and a one-tap Darood counter
- **Dark UI:** restrained design system with a single accent colour, flat sections and dense tables

### In progress
- All Outreach table (filters, soft delete with undo, trash, export)
- Follow-up reminders and notification bell
- Dashboard with outreach, productivity, time-tracking and counter charts
- Calendar with a per-day breakdown
- Daily log that replaces my Excel sheet, with import
- Backups, exports and settings

### Planned: AI features (opt-in)
- **Screenshot to entry:** drop in a screenshot of a sent email and a vision model extracts the company, recipient, sender, subject, body and date, then pre-fills the form for review
- **Ask FocusDesk:** chat with your own data ("how many emails did I send from my second Gmail this week?") using tool calling over a read-only database layer
- **Follow-up drafter:** generates a follow-up from the original email and your notes
- Works with your own API key or a local model; nothing is sent anywhere unless you enable it

## Tech stack

| Layer | Tools |
|---|---|
| UI | NiceGUI (runs locally in the browser) |
| Database | SQLite (single local file) |
| Charts | Plotly |
| Data / import / export | pandas, openpyxl |
| Desktop widget | tkinter |
| AI (planned) | Vision-capable LLM API or local model, with tool calling |

## Getting started

Requires Python 3.11+ on Windows.

```bash
git clone https://github.com/YOUR-USERNAME/focusdesk.git
cd focusdesk
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Open http://localhost:8080. The database is created automatically in `data/`.

Optional desktop widget:

```bash
python widget.py
```

Run `python check.py` after changes to catch missing functions or broken imports.

## Project structure

```text
focusdesk/
  main.py            app entry point
  widget.py          desktop stopwatch + counter
  check.py           sanity checker
  core/
    db.py            schema, defaults, connection helper
    repository.py    all SQL
    services.py      business logic (limits, warnings, validation)
    theme.py         design tokens and reusable UI components
    layout.py        sidebar, top bar, page shell
  pages/             one file per screen
  data/              local SQLite database (git-ignored)
```

## Design decisions

- **Offline-first.** Everything lives in one SQLite file; no accounts, no cloud.
- **Strict layers.** Pages never touch SQL, and services never touch UI.
- **Sender limits are computed, not stored.** "Sent today" is always a live query, so counts reset by themselves.
- **Soft delete.** Outreach entries can be restored from the trash.
- **Design restraint.** One accent colour, data-first layout, no decorative gradients.

## Privacy

All data stays on your machine. AI features are opt-in, use your own key, and can run against a local model.

## Roadmap

- [x] Foundation, theme and layout
- [x] Sender accounts
- [x] Add / edit outreach
- [x] Desktop widget
- [ ] All Outreach table
- [ ] Follow-ups and notifications
- [ ] Dashboard
- [ ] Calendar
- [ ] Daily log and Excel import
- [ ] Settings, backup and export
- [ ] AI: screenshot to entry
- [ ] AI: ask FocusDesk (chat over your data)
- [ ] Packaging as a single `.exe`

## Screenshots

_Coming soon._

## License

MIT

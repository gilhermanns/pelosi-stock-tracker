# Pelosi Stock Tracker

Automated daily tracker for Nancy Pelosi's congressional stock trade
disclosures. It pulls the public [House Stock Watcher](https://housestockwatcher.com/)
feed, isolates her trades, checks the newest one against a live market quote
and a short company profile, renders a summary chart, and emails you a
detailed alert whenever a **new** trade is filed.

> Deutsche Kurzanleitung weiter unten ↓ ([German setup guide](#deutsche-kurzanleitung))

## What it does

1. Downloads the full disclosure feed (no API key needed) and filters strictly to `representative == "Nancy Pelosi"`.
2. Finds the newest disclosed transaction and looks up:
   - a live market price via `yfinance`
   - a short company profile (sector, industry, business summary)
3. Renders `pelosi_portfolio.png` — a two-panel chart (transaction-type breakdown + monthly trade volume).
4. If the newest transaction is new since the last run, emails a formatted alert:

```
============================================================
NANCY PELOSI COPY-TRADE ALGORITHM ALERT
============================================================
Representative:   Nancy Pelosi
Ticker Symbol:    NVDA
Action Filed:     PURCHASE
Filing Date:      2026-07-01
Trade Date:       2026-06-01
Disclosed Amount: $1,000,001 - $5,000,000
------------------------------------------------------------
CURRENT MARKET CONTEXT:
Live Price:       $123.45
------------------------------------------------------------
COMPANY OVERVIEW:
Company:          NVIDIA Corporation
Sector:           Technology
Industry:         Semiconductors
About:            NVIDIA designs graphics processing units and AI hardware.

ACTION SUGGESTION:
This delayed public disclosure is informational only and is not an
instruction to buy, sell, or copy a transaction. Review source documents,
liquidity, valuation, suitability, and your own risk process independently.
Federal filing requirements mean this trade was originally executed
15 to 45 days prior to today's filing.
============================================================
```

## Repository layout

```
tracker.py                       # core application script
requirements.txt                 # Python dependencies
tests/test_tracker.py            # offline unit tests
.github/workflows/tracker.yml    # CI plus optional scheduled live run
```

## 1. Connect your email (one-time setup)

The tracker sends alerts over SMTP. Easiest option: a Gmail account with an
**App Password** (a normal Gmail password won't work with 2FA enabled, and
Google has removed "less secure app" logins entirely).

1. Enable **2-Step Verification**: <https://myaccount.google.com/security>
2. Create an App Password: <https://myaccount.google.com/apppasswords> (name it e.g. "Pelosi Tracker") and copy the 16-character code.
3. In this repo, go to **Settings → Secrets and variables → Actions → New repository secret** and add:

   | Secret name | Value |
   |---|---|
   | `SENDER_EMAIL` | The Gmail address you created the App Password for |
   | `RECEIVER_EMAIL` | Where you want alerts delivered (can be the same address) |
   | `SMTP_PASSWORD` | The 16-character App Password (not your normal Gmail password) |

Using a different provider? The script also honors optional `SMTP_HOST` and
`SMTP_PORT` env vars/secrets if you need something other than Gmail's
`smtp.gmail.com:465`.

## 2. Continuous tests and optional scheduled run

`.github/workflows/tracker.yml` runs the offline test suite on every push and
pull request. It also includes a daily, optional tracker job and a manual
workflow dispatch.

The scheduled live job is deliberately skipped until a maintainer configures
the repository variable `DISCLOSURE_DATA_URL` with a maintained normalized JSON
feed. This prevents a recurring failed job when an external aggregator changes
its access policy. A manual run can alternatively supply the URL as an input.

Each successful live run installs Python dependencies, runs `tracker.py` using
the configured source, and uploads the refreshed chart as an Action artifact.
It does not auto-commit market-derived output back into the source repository.

## 3. Running it locally (optional)

```bash
pip install -r requirements.txt
export SENDER_EMAIL="you@gmail.com"
export RECEIVER_EMAIL="you@gmail.com"
export SMTP_PASSWORD="your-16-char-app-password"
python tracker.py
```

For a maintained remote source, set `DISCLOSURE_DATA_URL` or use an explicit
argument:

```bash
python tracker.py --data-url "https://your-maintained-source.example/disclosures.json"
```

For a reproducible review, use a local normalized public disclosure export:

```bash
python tracker.py --data-file path/to/disclosures.json
```

The JSON must be a list of transaction records containing at least
`representative`, `transaction_date`, `disclosure_date`, `ticker`, `type`, and
`amount`. The tracker prints the newest disclosed trade, updates
`pelosi_portfolio.png`, and sends an email only if it is new since the last
recorded trade (tracked in the local `.last_seen_trade.txt`).

## 4. Why you won't get a daily email regardless

Alerts only fire when a genuinely **new** trade is disclosed — otherwise
you'd get the same trade re-sent every day. The chart still refreshes daily
regardless, so there's always a current visual snapshot even between
filings.

## Data & disclaimer

- Source: a maintainer-configured normalized public disclosure export. The prior
  House Stock Watcher S3 export returned HTTP 403 during validation, so it is no
  longer presented as an always-available dependency.
- Federal law gives members of Congress 15–45 days to file after executing a trade, so "Trade Date" is always historical.
- This tool is informational only — **not investment advice**.

---

## Deutsche Kurzanleitung

Dieses Tool prüft täglich automatisch die öffentlichen Handelsoffenlegungen
von Nancy Pelosi und schickt dir eine E-Mail, sobald ein **neuer** Trade
gemeldet wird — inklusive Aktie, investiertem Betrag, aktuellem Live-Kurs
und einer kurzen Firmenbeschreibung.

**Einrichtung in 3 Schritten:**

1. Gmail-App-Passwort erstellen: 2-Faktor-Authentifizierung aktivieren unter
   <https://myaccount.google.com/security>, dann App-Passwort erzeugen unter
   <https://myaccount.google.com/apppasswords>.
2. In diesem Repo unter **Settings → Secrets and variables → Actions** drei
   Secrets anlegen: `SENDER_EMAIL`, `RECEIVER_EMAIL`, `SMTP_PASSWORD`
   (das App-Passwort, nicht dein normales Passwort).
3. Fertig — der Workflow läuft ab sofort täglich automatisch (13:00 UTC)
   und kann jederzeit manuell über den **Actions**-Tab gestartet werden.

Du bekommst **nicht** jeden Tag eine Mail, sondern nur, wenn wirklich ein
neuer Trade gemeldet wurde. Der Chart (`pelosi_portfolio.png`) wird aber
täglich aktualisiert.

---

*Developed with support from Claude Code (Anthropic); the modelling choices, validation and documentation remain my responsibility.*

# Congressional Disclosure Monitor — Pelosi Stock Tracker

[![Disclosure Tracker](https://github.com/gilhermanns/pelosi-stock-tracker/actions/workflows/tracker.yml/badge.svg)](https://github.com/gilhermanns/pelosi-stock-tracker/actions/workflows/tracker.yml)

A small research utility for monitoring **delayed public congressional transaction disclosures** attributed to Nancy Pelosi. It adds a timestamped market-price snapshot and company context to a newly filed disclosure so that the public filing can be reviewed more efficiently.

> **Purpose and boundary:** This tool monitors public filings. It does not copy, score, rank or recommend transactions. A filing is historical — federal disclosure timing can mean that the underlying trade was made 15–45 days before the filing becomes public.

> Deutsche Kurzanleitung: [siehe unten](#deutsche-kurzanleitung).

## What a notification contains

When a newly filed transaction is detected, the monitor can send a neutral email notification with the following review fields:

| Field | Why it is included |
|---|---|
| Representative, ticker and transaction type | Identifies the disclosed transaction. |
| Transaction date and filing date | Makes the reporting delay visible. |
| Disclosed amount range | Preserves the public filing’s coarse disclosure range. |
| Point-in-time market price | Adds market context only; it is not a trading signal. |
| Company, sector and industry | Provides basic issuer context for source-document review. |

The generated chart summarises transaction-type counts and monthly filing activity. It is a descriptive visualisation, not a portfolio or performance chart.

## Data source and timing

- The workflow requires a maintainer-configured normalized JSON feed via `DISCLOSURE_DATA_URL`, or an explicit manual-run input.
- The previous House Stock Watcher S3 export returned HTTP 403 during validation and is **not** treated as a reliable default dependency.
- The repository ships an offline test path and supports local JSON exports for reproducible review.

## Installation and local run

```bash
git clone https://github.com/gilhermanns/pelosi-stock-tracker.git
cd pelosi-stock-tracker
python -m pip install -r requirements.txt
python -m pytest -q
```

For a reproducible local review, point the script at a normalized disclosure export:

```bash
python tracker.py --data-file path/to/disclosures.json
```

For a maintained remote source, use an environment variable or explicit argument:

```bash
export DISCLOSURE_DATA_URL="https://your-maintained-source.example/disclosures.json"
python tracker.py
# or: python tracker.py --data-url "https://your-maintained-source.example/disclosures.json"
```

The JSON must contain at least `representative`, `transaction_date`, `disclosure_date`, `ticker`, `type` and `amount`.

## Optional email notification

SMTP credentials are optional. Without them, the script still produces the chart and prints the newest disclosure; it simply skips email delivery.

| Secret or variable | Purpose |
|---|---|
| `SENDER_EMAIL` | Sender address for notifications |
| `RECEIVER_EMAIL` | Recipient address |
| `SMTP_PASSWORD` | SMTP app password or provider credential |
| `SMTP_HOST`, `SMTP_PORT` | Optional override for a non-default SMTP provider |

The GitHub workflow runs offline tests for every push and pull request. Its scheduled live-data job remains skipped until `DISCLOSURE_DATA_URL` is configured, preventing an external data-provider change from producing misleading recurring CI failures.

## Limitations

- Public disclosures may be delayed, amended, incomplete or unavailable through the configured feed.
- The price lookup is a contextual observation, not an entry, exit or valuation signal.
- Source documents, liquidity, valuation, suitability and an independent risk process must be considered separately.

---

## Deutsche Kurzanleitung

Das Tool beobachtet **verspätet veröffentlichte, öffentliche** Handelsoffenlegungen von Nancy Pelosi. Nach der Einrichtung einer Datenquelle kann es bei einer neu gemeldeten Transaktion eine neutrale E-Mail-Benachrichtigung mit Zeitstempel, Offenlegungsbetrag, Kurskontext und Firmeninformationen versenden. Es gibt **keine** Kauf-, Verkaufs- oder Kopierempfehlung aus.

1. Repository klonen und Abhängigkeiten installieren: `python -m pip install -r requirements.txt`.
2. Für einen reproduzierbaren Test eine lokale JSON-Datei verwenden: `python tracker.py --data-file path/to/disclosures.json`.
3. Erst für einen optionalen Live-Abruf `DISCLOSURE_DATA_URL` mit einem gepflegten, normalisierten Feed konfigurieren. Bis dahin führt der geplante Live-Job bewusst keinen externen Abruf aus.
4. Optional SMTP-Secrets konfigurieren, wenn Benachrichtigungen per E-Mail gewünscht sind.

---

*Developed with support from Claude Code (Anthropic); the modelling choices, validation and documentation remain my responsibility.*
*For research and educational purposes; not investment advice.*

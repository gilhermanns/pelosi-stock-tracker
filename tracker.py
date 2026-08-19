#!/usr/bin/env python3
"""
Nancy Pelosi Congressional Disclosure Monitor
==============================================
Consumes a configured public-disclosure JSON feed, isolates transactions
filed under Nancy Pelosi, adds a point-in-time market quote via yfinance,
renders a summary chart, and can email a neutral notification when a new
disclosure is detected.

The maintained source is supplied through --data-url, --data-file or
DISCLOSURE_DATA_URL. The historical House Stock Watcher fallback is retained
only to provide a clear configuration error when no maintained source is set.
"""

import os
import smtplib
import sys
import argparse
import json
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless rendering for CI/CD runners
import matplotlib.pyplot as plt
import pandas as pd
import requests
import yfinance as yf

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATA_URL = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
REPRESENTATIVE_NAME = "Nancy Pelosi"
CHART_OUTPUT_PATH = "pelosi_portfolio.png"
LAST_SEEN_FILE = ".last_seen_trade.txt"  # tracks the last notified transaction id
REQUEST_TIMEOUT_SECONDS = 30


# ---------------------------------------------------------------------------
# Data sourcing
# ---------------------------------------------------------------------------
def fetch_all_transactions(
    data_url: str | None = None, data_file: str | None = None
) -> pd.DataFrame:
    """Load a normalized public disclosure export from a URL or local JSON file.

    ``data_file`` is intentionally supported because third-party disclosure feeds
    can change access rules. It accepts a JSON list of transaction records with the
    same schema as the previous feed; no synthetic transactions are created.
    """
    if data_file:
        path = Path(data_file)
        if not path.is_file():
            raise FileNotFoundError(f"Disclosure JSON file not found: {path}")
        print(f"Loading disclosure data from {path} ...")
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    else:
        source_url = data_url or os.environ.get("DISCLOSURE_DATA_URL") or DATA_URL
        print(f"Fetching disclosure feed from {source_url} ...")
        try:
            response = requests.get(source_url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(
                "The configured disclosure feed is unavailable. Supply a maintained "
                "normalized feed with DISCLOSURE_DATA_URL or pass --data-file with a "
                "public disclosure JSON export. No trade data was generated."
            ) from exc

    if not isinstance(payload, list):
        raise ValueError("Unexpected data schema: expected a JSON list of transactions.")

    df = pd.DataFrame(payload)
    print(f"Retrieved {len(df)} total transactions across all representatives.")
    return df


def filter_pelosi_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Strictly filter the raw feed down to Nancy Pelosi's disclosed trades."""
    if "representative" not in df.columns:
        raise ValueError("Unexpected data schema: 'representative' column missing.")

    mask = df["representative"].str.contains(REPRESENTATIVE_NAME, case=False, na=False)
    pelosi_df = df.loc[mask].copy()

    # Normalize dates so we can reliably sort for the "newest" transaction.
    pelosi_df["transaction_date"] = pd.to_datetime(pelosi_df["transaction_date"], errors="coerce")
    pelosi_df["disclosure_date"] = pd.to_datetime(pelosi_df["disclosure_date"], errors="coerce")
    pelosi_df = pelosi_df.dropna(subset=["transaction_date"])
    pelosi_df = pelosi_df.sort_values("transaction_date", ascending=False)

    print(f"Filtered to {len(pelosi_df)} transactions for {REPRESENTATIVE_NAME}.")
    return pelosi_df


def get_newest_transaction(pelosi_df: pd.DataFrame) -> pd.Series:
    """Return the single most recent trade transaction from the filtered set."""
    if pelosi_df.empty:
        raise ValueError(f"No transactions found for {REPRESENTATIVE_NAME}.")
    return pelosi_df.iloc[0]


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------
def get_live_price(ticker: str) -> float | None:
    """Fetch the latest real-time (or most recent close) market price for a ticker."""
    ticker = (ticker or "").strip().upper()
    if not ticker or ticker in {"N/A", "--"}:
        print(f"Skipping market lookup: no valid ticker present ('{ticker}').")
        return None

    try:
        asset = yf.Ticker(ticker)

        # fast_info offers the closest thing to a real-time quote without
        # pulling a full historical download.
        price = getattr(asset.fast_info, "last_price", None)
        if price:
            return float(price)

        # Fallback: most recent daily close if fast_info is unavailable.
        history = asset.history(period="5d")
        if not history.empty:
            return float(history["Close"].iloc[-1])

    except Exception as exc:  # yfinance / network hiccups shouldn't crash the run
        print(f"Warning: could not fetch live price for {ticker}: {exc}")

    return None


def get_company_info(ticker: str) -> dict:
    """Fetch a short company profile (name, sector, industry, blurb) for the ticker."""
    ticker = (ticker or "").strip().upper()
    info: dict = {"name": "N/A", "sector": "N/A", "industry": "N/A", "summary": "No company information available."}

    if not ticker or ticker in {"N/A", "--"}:
        return info

    try:
        raw_info = yf.Ticker(ticker).info
        info["name"] = raw_info.get("longName") or raw_info.get("shortName") or ticker
        info["sector"] = raw_info.get("sector", "N/A")
        info["industry"] = raw_info.get("industry", "N/A")

        summary = raw_info.get("longBusinessSummary", "")
        if summary:
            # Trim to the first couple of sentences so the email stays skimmable.
            sentences = summary.split(". ")
            info["summary"] = ". ".join(sentences[:2]).rstrip(".") + "."
    except Exception as exc:
        print(f"Warning: could not fetch company info for {ticker}: {exc}")

    return info


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------
def build_summary_chart(pelosi_df: pd.DataFrame, output_path: str = CHART_OUTPUT_PATH) -> None:
    """Render a two-panel summary chart: action breakdown + trade volume over time."""
    plt.style.use("dark_background")
    fig, (ax_actions, ax_timeline) = plt.subplots(
        1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [1, 1.4]}
    )
    fig.suptitle(
        "Nancy Pelosi — Congressional Trade Disclosure Summary",
        fontsize=16,
        fontweight="bold",
        color="white",
    )

    # --- Left panel: breakdown of disclosed transaction types ---
    action_counts = pelosi_df["type"].value_counts()
    palette = ["#00c896", "#ff5c5c", "#4da6ff", "#f5c542", "#a374ff"]
    colors = [palette[i % len(palette)] for i in range(len(action_counts))]

    ax_actions.pie(
        action_counts.values,
        labels=action_counts.index,
        autopct="%1.0f%%",
        colors=colors,
        startangle=90,
        textprops={"color": "white", "fontsize": 10},
        wedgeprops={"edgecolor": "black", "linewidth": 1},
    )
    ax_actions.set_title("Transaction Action Breakdown", color="white", fontsize=12)

    # --- Right panel: trade count by month over the most recent history ---
    timeline_df = pelosi_df.copy()
    timeline_df["month"] = timeline_df["transaction_date"].dt.to_period("M")
    monthly_counts = timeline_df.groupby("month").size().sort_index().tail(18)

    ax_timeline.bar(
        monthly_counts.index.astype(str),
        monthly_counts.values,
        color="#4da6ff",
        edgecolor="black",
    )
    ax_timeline.set_title("Disclosed Trade Volume (Last 18 Months)", color="white", fontsize=12)
    ax_timeline.set_ylabel("Number of Transactions", color="white")
    ax_timeline.tick_params(axis="x", rotation=45, colors="white")
    ax_timeline.tick_params(axis="y", colors="white")
    ax_timeline.grid(axis="y", alpha=0.3)

    fig.text(
        0.5,
        0.02,
        f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · Source: House Stock Watcher",
        ha="center",
        fontsize=8,
        color="gray",
    )

    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(output_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved summary chart to {output_path}")


# ---------------------------------------------------------------------------
# Email notifications
# ---------------------------------------------------------------------------
def format_notification_email(
    transaction: pd.Series, live_price: float | None, company_info: dict
) -> str:
    """Render a neutral fixed-width notification for the newest disclosure."""
    ticker = str(transaction.get("ticker", "N/A")).upper()
    action = str(transaction.get("type", "N/A")).upper()
    filing_date = transaction.get("disclosure_date")
    trade_date = transaction.get("transaction_date")
    amount = transaction.get("amount", "N/A")

    filing_date_str = filing_date.strftime("%Y-%m-%d") if pd.notna(filing_date) else "N/A"
    trade_date_str = trade_date.strftime("%Y-%m-%d") if pd.notna(trade_date) else "N/A"
    price_str = f"{live_price:,.2f}" if live_price is not None else "N/A"

    return f"""============================================================
NANCY PELOSI PUBLIC DISCLOSURE MONITOR
============================================================
Representative:   Nancy Pelosi
Ticker Symbol:    {ticker}
Action Filed:     {action}
Filing Date:      {filing_date_str}
Trade Date:       {trade_date_str}
Disclosed Amount: {amount}
------------------------------------------------------------
CURRENT MARKET CONTEXT:
Live Price:       ${price_str}
------------------------------------------------------------
COMPANY OVERVIEW:
Company:          {company_info['name']}
Sector:           {company_info['sector']}
Industry:         {company_info['industry']}
About:            {company_info['summary']}

RESEARCH BOUNDARY:
This delayed public disclosure is informational only. It does not
rank, score or recommend a transaction. Review source documents,
liquidity, valuation, suitability and your own risk process independently.
Federal filing requirements mean this transaction may have been executed
15 to 45 days before today's filing.
============================================================
"""


def send_email_notification(subject: str, body: str) -> None:
    """Dispatch the disclosure notification via environment-provided SMTP credentials."""
    sender_email = os.environ.get("SENDER_EMAIL")
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")

    if not all([sender_email, receiver_email, smtp_password]):
        print(
            "Skipping email dispatch: SENDER_EMAIL, RECEIVER_EMAIL, and/or "
            "SMTP_PASSWORD environment variables are not set."
        )
        return

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email

    try:
        # Default assumes Gmail's SMTP-over-SSL endpoint; override via env vars
        # if a different provider is used.
        smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "465"))

        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(sender_email, smtp_password)
            server.sendmail(sender_email, [receiver_email], msg.as_string())

        print(f"Disclosure notification sent to {receiver_email}.")
    except Exception as exc:
        print(f"Error sending disclosure notification: {exc}")


# ---------------------------------------------------------------------------
# New-disclosure detection (avoids duplicate notifications on scheduled runs)
# ---------------------------------------------------------------------------
def transaction_id(transaction: pd.Series) -> str:
    """Build a stable identifier for a transaction to detect duplicates across runs."""
    return "|".join(
        str(transaction.get(field, ""))
        for field in ("ticker", "transaction_date", "disclosure_date", "type", "amount")
    )


def is_new_transaction(transaction: pd.Series) -> bool:
    """Check the last-seen marker file to avoid duplicate notifications."""
    current_id = transaction_id(transaction)

    if not os.path.exists(LAST_SEEN_FILE):
        return True

    with open(LAST_SEEN_FILE, "r") as f:
        last_id = f.read().strip()

    return current_id != last_id


def record_seen_transaction(transaction: pd.Series) -> None:
    """Persist the newest transaction id so future runs do not notify twice."""
    with open(LAST_SEEN_FILE, "w") as f:
        f.write(transaction_id(transaction))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize public Nancy Pelosi transaction disclosures."
    )
    parser.add_argument(
        "--data-url",
        help="Optional URL for a maintained normalized JSON disclosure feed.",
    )
    parser.add_argument(
        "--data-file",
        help="Optional local normalized JSON disclosure export for reproducible runs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        raw_df = fetch_all_transactions(data_url=args.data_url, data_file=args.data_file)
        pelosi_df = filter_pelosi_transactions(raw_df)
    except Exception as exc:
        print(f"Fatal error while sourcing/filtering data: {exc}", file=sys.stderr)
        return 1

    # Chart is always regenerated so the repo's visual snapshot stays current.
    build_summary_chart(pelosi_df)

    newest_transaction = get_newest_transaction(pelosi_df)
    ticker = str(newest_transaction.get("ticker", "")).upper()

    print(
        f"Newest disclosed transaction: {ticker} | "
        f"{newest_transaction.get('type')} | "
        f"trade date {newest_transaction.get('transaction_date')}"
    )

    if not is_new_transaction(newest_transaction):
        print("No new disclosure since the last run. No email notification will be sent.")
        return 0

    live_price = get_live_price(ticker)
    company_info = get_company_info(ticker)
    email_body = format_notification_email(newest_transaction, live_price, company_info)
    print(email_body)

    send_email_notification(
        subject=f"Pelosi public disclosure: {ticker} {newest_transaction.get('type')}",
        body=email_body,
    )

    record_seen_transaction(newest_transaction)
    return 0


if __name__ == "__main__":
    sys.exit(main())

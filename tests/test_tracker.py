import json

import pandas as pd
import pytest

import tracker


def sample_transactions():
    return [
        {
            "representative": "Nancy Pelosi",
            "transaction_date": "2026-01-15",
            "disclosure_date": "2026-02-01",
            "ticker": "AAPL",
            "type": "Purchase",
            "amount": "$1,001 - $15,000",
        },
        {
            "representative": "Other Member",
            "transaction_date": "2026-01-16",
            "disclosure_date": "2026-02-02",
            "ticker": "MSFT",
            "type": "Sale",
            "amount": "$1,001 - $15,000",
        },
    ]


def test_fetch_all_transactions_supports_local_json(tmp_path):
    data_file = tmp_path / "disclosures.json"
    data_file.write_text(json.dumps(sample_transactions()), encoding="utf-8")

    frame = tracker.fetch_all_transactions(data_file=str(data_file))

    assert len(frame) == 2
    assert set(frame["representative"]) == {"Nancy Pelosi", "Other Member"}


def test_fetch_all_transactions_explains_unavailable_remote_source(monkeypatch):
    def raise_network_error(*args, **kwargs):
        raise tracker.requests.ConnectionError("source unavailable")

    monkeypatch.setattr(tracker.requests, "get", raise_network_error)

    with pytest.raises(RuntimeError, match="DISCLOSURE_DATA_URL"):
        tracker.fetch_all_transactions(data_url="https://example.invalid/feed.json")


def test_filter_and_alert_are_informational():
    filtered = tracker.filter_pelosi_transactions(pd.DataFrame(sample_transactions()))
    newest = tracker.get_newest_transaction(filtered)
    body = tracker.format_alert_email(newest, 123.45, {"name": "Apple", "sector": "Tech", "industry": "Hardware", "summary": "Example."})

    assert newest["ticker"] == "AAPL"
    assert "informational only" in body
    assert "instruction to buy" in body

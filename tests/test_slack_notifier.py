import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import scripts.slack_notifier as sn


# ---------------------------------------------------------------------------
# build_slack_message
# ---------------------------------------------------------------------------

def test_build_slack_message_no_results():
    msg = sn.build_slack_message([])
    assert msg["text"] == "System Update Report"
    block_texts = [
        b.get("text", {}).get("text", "")
        for b in msg["blocks"]
        if b["type"] == "section"
    ]
    assert any("No systems" in t for t in block_texts)


def test_build_slack_message_summary_fields(sample_results):
    msg = sn.build_slack_message(sample_results)
    # Find the summary section (has "fields" key)
    summary_section = next(b for b in msg["blocks"] if b.get("fields"))
    field_texts = [f["text"] for f in summary_section["fields"]]
    combined = "\n".join(field_texts)
    assert "3" in combined   # hosts scanned
    assert "8" in combined   # total updates (5+3+0)
    assert "3" in combined   # security updates (2+1+0)
    assert "1" in combined   # reboot needed


def test_build_slack_message_emoji_reboot(sample_results):
    # sample_results has a host needing reboot → rotating_light
    msg = sn.build_slack_message(sample_results)
    header_block = next(b for b in msg["blocks"] if b["type"] == "header")
    assert ":rotating_light:" in header_block["text"]["text"]


def test_build_slack_message_emoji_updates_only():
    results = [{"hostname": "h", "updates_installed": 3, "security_updates": 0, "reboot_required": False}]
    msg = sn.build_slack_message(results)
    header_block = next(b for b in msg["blocks"] if b["type"] == "header")
    assert ":zap:" in header_block["text"]["text"]


def test_build_slack_message_emoji_all_good():
    results = [{"hostname": "h", "updates_installed": 0, "security_updates": 0, "reboot_required": False}]
    msg = sn.build_slack_message(results)
    header_block = next(b for b in msg["blocks"] if b["type"] == "header")
    assert ":white_check_mark:" in header_block["text"]["text"]


def test_build_slack_message_limits_host_detail_blocks(sample_results):
    # Pad to 8 hosts; detail blocks should be capped at 5
    many_results = sample_results * 3  # 9 hosts
    msg = sn.build_slack_message(many_results)
    section_blocks = [b for b in msg["blocks"] if b["type"] == "section" and b.get("text")]
    # Should contain an "And X more hosts..." block
    overflow_blocks = [b for b in section_blocks if "more hosts" in b["text"].get("text", "")]
    assert len(overflow_blocks) == 1


def test_build_slack_message_no_overflow_when_few_hosts():
    results = [{"hostname": "h1", "updates_installed": 0, "security_updates": 0, "reboot_required": False}]
    msg = sn.build_slack_message(results)
    section_blocks = [b for b in msg["blocks"] if b["type"] == "section"]
    overflow = [b for b in section_blocks if "more hosts" in b.get("text", {}).get("text", "")]
    assert len(overflow) == 0


def test_build_slack_message_sorted_by_updates_desc():
    results = [
        {"hostname": "low", "updates_installed": 1, "security_updates": 0, "reboot_required": False},
        {"hostname": "high", "updates_installed": 10, "security_updates": 0, "reboot_required": False},
    ]
    msg = sn.build_slack_message(results)
    section_texts = [
        b["text"]["text"] for b in msg["blocks"]
        if b["type"] == "section" and b.get("text") and "Updates:" in b["text"]["text"]
    ]
    assert section_texts[0].startswith("high")


# ---------------------------------------------------------------------------
# send_to_slack
# ---------------------------------------------------------------------------

def test_send_to_slack_no_webhook(monkeypatch):
    monkeypatch.setattr(sn, "SLACK_WEBHOOK_URL", "")
    result = sn.send_to_slack({"text": "test"})
    assert result is False


def test_send_to_slack_success(monkeypatch):
    monkeypatch.setattr(sn, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    mock_response = MagicMock()
    mock_response.status_code = 200
    with patch("scripts.slack_notifier.requests.post", return_value=mock_response) as mock_post:
        result = sn.send_to_slack({"text": "hello"})
    assert result is True
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {"text": "hello"}
    assert kwargs["timeout"] == 10


def test_send_to_slack_non_200(monkeypatch):
    monkeypatch.setattr(sn, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    with patch("scripts.slack_notifier.requests.post", return_value=mock_response):
        result = sn.send_to_slack({"text": "hello"})
    assert result is False


def test_send_to_slack_network_error(monkeypatch):
    monkeypatch.setattr(sn, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    with patch("scripts.slack_notifier.requests.post", side_effect=Exception("timeout")):
        result = sn.send_to_slack({"text": "hello"})
    assert result is False


# ---------------------------------------------------------------------------
# load_latest_results
# ---------------------------------------------------------------------------

def test_load_latest_results(reports_dir, monkeypatch):
    monkeypatch.setattr(sn, "REPORTS_DIR", str(reports_dir))
    results = sn.load_latest_results()
    assert len(results) == 3


def test_load_latest_results_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(sn, "REPORTS_DIR", str(tmp_path))
    assert sn.load_latest_results() == []


def test_load_latest_results_capped_at_10(tmp_path, monkeypatch):
    import json
    for i in range(15):
        (tmp_path / f"host{i:02d}_update_result.json").write_text(json.dumps({"hostname": f"h{i}"}))
    monkeypatch.setattr(sn, "REPORTS_DIR", str(tmp_path))
    results = sn.load_latest_results()
    assert len(results) == 10

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import scripts.generate_reports as gr


# ---------------------------------------------------------------------------
# calculate_stats
# ---------------------------------------------------------------------------

def test_calculate_stats_empty():
    stats = gr.calculate_stats([])
    assert stats == {
        "total_hosts": 0,
        "total_updates": 0,
        "total_security": 0,
        "hosts_needing_reboot": 0,
    }


def test_calculate_stats_single_host(sample_results):
    stats = gr.calculate_stats([sample_results[0]])
    assert stats["total_hosts"] == 1
    assert stats["total_updates"] == 5
    assert stats["total_security"] == 2
    assert stats["hosts_needing_reboot"] == 0


def test_calculate_stats_multiple_hosts(sample_results):
    stats = gr.calculate_stats(sample_results)
    assert stats["total_hosts"] == 3
    assert stats["total_updates"] == 8   # 5 + 3 + 0
    assert stats["total_security"] == 3  # 2 + 1 + 0
    assert stats["hosts_needing_reboot"] == 1


def test_calculate_stats_missing_keys():
    # Fields should default to 0 when absent
    stats = gr.calculate_stats([{"hostname": "bare-host"}])
    assert stats["total_updates"] == 0
    assert stats["total_security"] == 0
    assert stats["hosts_needing_reboot"] == 0


# ---------------------------------------------------------------------------
# get_status_color
# ---------------------------------------------------------------------------

def test_status_color_reboot_required():
    assert gr.get_status_color({"reboot_required": True, "updates_installed": 0}) == "#ff6b6b"


def test_status_color_updates_installed():
    assert gr.get_status_color({"reboot_required": False, "updates_installed": 3}) == "#ffd93d"


def test_status_color_up_to_date():
    assert gr.get_status_color({"reboot_required": False, "updates_installed": 0}) == "#6bcf7f"


def test_status_color_reboot_takes_priority_over_updates():
    # Reboot flag should win even when updates_installed > 0
    assert gr.get_status_color({"reboot_required": True, "updates_installed": 5}) == "#ff6b6b"


# ---------------------------------------------------------------------------
# generate_html
# ---------------------------------------------------------------------------

def test_generate_html_contains_hostnames(sample_results):
    stats = gr.calculate_stats(sample_results)
    html = gr.generate_html(sample_results, stats)
    for host in sample_results:
        assert host["hostname"] in html


def test_generate_html_contains_stats(sample_results):
    stats = gr.calculate_stats(sample_results)
    html = gr.generate_html(sample_results, stats)
    assert str(stats["total_hosts"]) in html
    assert str(stats["total_updates"]) in html
    assert str(stats["total_security"]) in html


def test_generate_html_empty_results():
    stats = gr.calculate_stats([])
    html = gr.generate_html([], stats)
    assert "No hosts have been scanned yet" in html


def test_generate_html_reboot_status(sample_results):
    stats = gr.calculate_stats(sample_results)
    html = gr.generate_html(sample_results, stats)
    # db-01 requires reboot, so "Yes" must appear (and "No" for others)
    assert "Yes" in html
    assert "No" in html


def test_generate_html_update_interval(monkeypatch, sample_results):
    monkeypatch.setenv("UPDATE_INTERVAL", "1800")
    stats = gr.calculate_stats(sample_results)
    html = gr.generate_html(sample_results, stats)
    assert "1800" in html


# ---------------------------------------------------------------------------
# load_results
# ---------------------------------------------------------------------------

def test_load_results_reads_json_files(reports_dir, monkeypatch):
    monkeypatch.setattr(gr, "REPORTS_DIR", str(reports_dir))
    results = gr.load_results()
    assert len(results) == 3
    hostnames = {r["hostname"] for r in results}
    assert hostnames == {"web-01", "db-01", "monitor-01"}


def test_load_results_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(gr, "REPORTS_DIR", str(tmp_path))
    assert gr.load_results() == []


def test_load_results_skips_invalid_json(tmp_path, monkeypatch):
    (tmp_path / "bad_update_result.json").write_text("not json{{{")
    (tmp_path / "good_update_result.json").write_text('{"hostname": "good"}')
    monkeypatch.setattr(gr, "REPORTS_DIR", str(tmp_path))
    results = gr.load_results()
    assert len(results) == 1
    assert results[0]["hostname"] == "good"

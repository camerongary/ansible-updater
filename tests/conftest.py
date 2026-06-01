import pytest
import json
import os


SAMPLE_HOST_DEBIAN = {
    "hostname": "web-01",
    "timestamp": "2026-06-01T10:00:00",
    "os_family": "Debian",
    "os_name": "Ubuntu 22.04",
    "updates_available": 5,
    "security_updates": 2,
    "updates_installed": 5,
    "reboot_required": False,
    "kernel": "5.15.0-91-generic",
    "ip_address": "192.168.12.10",
}

SAMPLE_HOST_REDHAT = {
    "hostname": "db-01",
    "timestamp": "2026-06-01T10:01:00",
    "os_family": "RedHat",
    "os_name": "CentOS 8.5",
    "updates_available": 3,
    "security_updates": 1,
    "updates_installed": 3,
    "reboot_required": True,
    "kernel": "4.18.0-348",
    "ip_address": "192.168.12.20",
}

SAMPLE_HOST_UP_TO_DATE = {
    "hostname": "monitor-01",
    "timestamp": "2026-06-01T10:02:00",
    "os_family": "Debian",
    "os_name": "Debian 12",
    "updates_available": 0,
    "security_updates": 0,
    "updates_installed": 0,
    "reboot_required": False,
    "kernel": "6.1.0-18-amd64",
    "ip_address": "192.168.12.30",
}


@pytest.fixture
def sample_results():
    return [SAMPLE_HOST_DEBIAN, SAMPLE_HOST_REDHAT, SAMPLE_HOST_UP_TO_DATE]


@pytest.fixture
def reports_dir(tmp_path):
    """Temp directory pre-populated with result JSON files."""
    for host in [SAMPLE_HOST_DEBIAN, SAMPLE_HOST_REDHAT, SAMPLE_HOST_UP_TO_DATE]:
        filename = f"{host['hostname']}_update_result.json"
        (tmp_path / filename).write_text(json.dumps(host))
    return tmp_path

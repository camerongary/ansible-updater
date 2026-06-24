#!/usr/bin/env python3
"""Append-only audit log shared by the dashboard and the orchestrator.

Importable (web_server.py calls ``audit.append(...)``) and runnable as a CLI so
the bash poller in start.sh can log apply/reboot outcomes:

    python3 /scripts/audit.py --action apply --host 192.168.12.10 \
        --packages openssl,bash --source auto --result success --detail "rc=0"

Records are written one JSON object per line to ``$REPORTS_DIR/audit_log.jsonl``
so the history survives container restarts via the mounted /reports volume.
"""

import argparse
import json
import os
import sys
from datetime import datetime

REPORTS_DIR = os.environ.get("REPORTS_DIR", "/reports")
AUDIT_LOG = os.path.join(REPORTS_DIR, "audit_log.jsonl")

VALID_ACTIONS = {"approve", "reject", "apply", "reboot", "recheck", "autoupdate", "autoreboot"}
VALID_RESULTS = {"requested", "success", "failure"}


def append(action, host, packages=None, source="dashboard", result="requested", detail=""):
    """Append a single audit record. Never raises on I/O issues (best effort)."""
    record = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "action": action,
        "host": host,
        "packages": list(packages) if packages else [],
        "source": source,
        "result": result,
        "detail": detail,
    }
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:  # logging must never break the caller
        print(f"audit: failed to write record: {e}", file=sys.stderr)
    return record


def read(limit=50):
    """Return the most recent ``limit`` records, newest first."""
    if not os.path.exists(AUDIT_LOG):
        return []
    try:
        with open(AUDIT_LOG, "r") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"audit: failed to read log: {e}", file=sys.stderr)
        return []

    records = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    records.reverse()
    return records


def _main():
    parser = argparse.ArgumentParser(description="Append an audit log record")
    parser.add_argument("--action", required=True, choices=sorted(VALID_ACTIONS))
    parser.add_argument("--host", required=True)
    parser.add_argument("--packages", default="", help="comma-separated package names")
    parser.add_argument("--source", default="auto")
    parser.add_argument("--result", default="success", choices=sorted(VALID_RESULTS))
    parser.add_argument("--detail", default="")
    args = parser.parse_args()

    packages = [p for p in args.packages.split(",") if p]
    append(
        action=args.action,
        host=args.host,
        packages=packages,
        source=args.source,
        result=args.result,
        detail=args.detail,
    )


if __name__ == "__main__":
    _main()

#!/usr/bin/env python3

"""
Prometheus metrics exporter for Ansible Update Manager
Exposes metrics in Prometheus format on port 8081
"""

import json
import os
import glob
from datetime import datetime
from flask import Flask, Response
from pathlib import Path

app = Flask(__name__)
REPORTS_DIR = "/reports"

# Prometheus metrics
class PrometheusMetrics:
    def __init__(self):
        self.metrics = {}

    def gauge(self, name, value, help_text="", labels=None):
        """Add a gauge metric"""
        if help_text:
            if name not in self.metrics:
                self.metrics[name] = {"type": "gauge", "help": help_text, "values": []}
        
        label_str = ""
        if labels:
            label_pairs = [f'{k}="{v}"' for k, v in labels.items()]
            label_str = "{" + ",".join(label_pairs) + "}"
        
        self.metrics.setdefault(name, {"type": "gauge", "help": "", "values": []})["values"].append(
            (label_str, value)
        )

    def counter(self, name, value, help_text="", labels=None):
        """Add a counter metric"""
        if help_text:
            if name not in self.metrics:
                self.metrics[name] = {"type": "counter", "help": help_text, "values": []}
        
        label_str = ""
        if labels:
            label_pairs = [f'{k}="{v}"' for k, v in labels.items()]
            label_str = "{" + ",".join(label_pairs) + "}"
        
        self.metrics.setdefault(name, {"type": "counter", "help": "", "values": []})["values"].append(
            (label_str, value)
        )

    def render(self):
        """Render metrics in Prometheus format"""
        output = []
        
        for metric_name, metric_data in sorted(self.metrics.items()):
            # Add help and type comments
            if metric_data["help"]:
                output.append(f"# HELP {metric_name} {metric_data['help']}")
            output.append(f"# TYPE {metric_name} {metric_data['type']}")
            
            # Add metric values
            for labels, value in metric_data["values"]:
                if labels:
                    output.append(f"{metric_name}{labels} {value}")
                else:
                    output.append(f"{metric_name} {value}")
            
            output.append("")
        
        return "\n".join(output)


def load_results():
    """Load all update result JSON files"""
    results = []
    json_files = glob.glob(os.path.join(REPORTS_DIR, "*_update_result.json"))
    
    for json_file in sorted(json_files, reverse=True):
        try:
            with open(json_file, 'r') as f:
                results.append(json.load(f))
        except Exception as e:
            print(f"Error loading {json_file}: {e}")
    
    return results


def generate_metrics():
    """Generate Prometheus metrics from results"""
    metrics = PrometheusMetrics()
    results = load_results()
    
    # System-wide metrics
    metrics.gauge(
        "ansible_updater_hosts_total",
        len(results),
        help_text="Total number of hosts scanned"
    )
    
    metrics.gauge(
        "ansible_updater_updates_total",
        sum(r.get("updates_installed", 0) for r in results),
        help_text="Total updates applied across all hosts"
    )
    
    metrics.gauge(
        "ansible_updater_security_updates_total",
        sum(r.get("security_updates", 0) for r in results),
        help_text="Total security updates available"
    )
    
    metrics.gauge(
        "ansible_updater_hosts_needing_reboot",
        sum(1 for r in results if r.get("reboot_required", False)),
        help_text="Number of hosts requiring reboot"
    )
    
    # Per-host metrics
    for host in results:
        hostname = host.get("hostname", "unknown")
        os_name = host.get("os_name", "unknown")
        
        metrics.gauge(
            "ansible_updater_host_updates_installed",
            host.get("updates_installed", 0),
            help_text="Updates installed on host",
            labels={"host": hostname, "os": os_name}
        )
        
        metrics.gauge(
            "ansible_updater_host_security_updates",
            host.get("security_updates", 0),
            help_text="Security updates available on host",
            labels={"host": hostname, "os": os_name}
        )
        
        metrics.gauge(
            "ansible_updater_host_reboot_required",
            1 if host.get("reboot_required", False) else 0,
            help_text="Host reboot required (1=true, 0=false)",
            labels={"host": hostname, "os": os_name}
        )
        
        # Parse timestamp and calculate age
        try:
            timestamp = datetime.fromisoformat(host.get("timestamp", ""))
            age_seconds = (datetime.utcnow() - timestamp).total_seconds()
            metrics.gauge(
                "ansible_updater_host_last_scan_age_seconds",
                int(age_seconds),
                help_text="Seconds since last scan",
                labels={"host": hostname, "os": os_name}
            )
        except:
            pass
    
    return metrics


@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    metrics = generate_metrics()
    return Response(metrics.render(), mimetype='text/plain; charset=utf-8')


@app.route('/health')
def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.route('/')
def index():
    """Simple index page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ansible Updater Metrics</title>
    </head>
    <body>
        <h1>Ansible Update Manager - Prometheus Metrics</h1>
        <p><a href="/metrics">View Metrics</a></p>
        <p><a href="/health">Health Check</a></p>
    </body>
    </html>
    """


if __name__ == '__main__':
    print("Starting Prometheus metrics exporter on 0.0.0.0:8081")
    print("Metrics available at: http://localhost:8081/metrics")
    app.run(host='0.0.0.0', port=8081, debug=False)

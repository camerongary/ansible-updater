#!/usr/bin/env python3

import json
import os
import glob
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
from pathlib import Path

TRIGGER_FILE = "/tmp/trigger_scan"
LOCK_FILE = "/tmp/scan_running"

app = Flask(__name__)
REPORTS_DIR = "/reports"

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

@app.route('/')
def index():
    """Serve the main dashboard"""
    results = load_results()
    
    # Calculate stats
    stats = {
        "total_hosts": len(results),
        "total_updates": sum(r.get("updates_installed", 0) for r in results),
        "total_security": sum(r.get("security_updates", 0) for r in results),
        "hosts_needing_reboot": sum(1 for r in results if r.get("reboot_required", False))
    }
    
    # Generate table rows
    table_rows = ""
    for host in results:
        reboot_status = "Yes" if host.get("reboot_required") else "No"
        reboot_badge_class = "status-danger" if host.get("reboot_required") else "status-success"
        
        updates = host.get("updates_installed", 0)
        
        if updates > 0:
            status_class = "status-warning"
            status_text = "Updates Applied"
        elif host.get("reboot_required"):
            status_class = "status-danger"
            status_text = "Reboot Needed"
        else:
            status_class = "status-success"
            status_text = "Up to Date"
        
        table_rows += f"""
                    <tr>
                        <td><strong>{host.get('hostname', 'Unknown')}</strong></td>
                        <td>{host.get('os_name', 'Unknown')}</td>
                        <td>{host.get('ip_address', 'N/A')}</td>
                        <td><span class="number-badge">{updates}</span></td>
                        <td><span class="number-badge">{host.get('security_updates', 0)}</span></td>
                        <td><span class="status-badge {reboot_badge_class}">{reboot_status}</span></td>
                        <td><span class="status-badge {status_class}">{status_text}</span></td>
                        <td>{host.get('timestamp', 'N/A')}</td>
                    </tr>
        """
    
    if not results:
        table_rows = '<tr><td colspan="8" style="text-align: center; padding: 40px; color: #999;">No hosts have been scanned yet</td></tr>'
    
    update_interval = os.environ.get("UPDATE_INTERVAL", "3600")
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Update Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 30px;
        }}
        
        header h1 {{
            color: #333;
            margin-bottom: 10px;
        }}
        
        header p {{
            color: #666;
            font-size: 14px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            text-align: center;
        }}
        
        .stat-card h3 {{
            color: #666;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }}
        
        .stat-card .value {{
            font-size: 36px;
            font-weight: bold;
            color: #667eea;
        }}
        
        .hosts-table {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        
        .table-header {{
            background: #f8f9fa;
            padding: 20px 30px;
            border-bottom: 1px solid #e9ecef;
        }}
        
        .table-header h2 {{
            color: #333;
            font-size: 18px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        thead {{
            background: #f8f9fa;
        }}
        
        th {{
            padding: 15px 30px;
            text-align: left;
            font-weight: 600;
            color: #666;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid #e9ecef;
        }}
        
        td {{
            padding: 15px 30px;
            border-bottom: 1px solid #e9ecef;
            color: #555;
        }}
        
        tbody tr:hover {{
            background: #f8f9fa;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .status-success {{
            background: #e8f9f0;
            color: #1a9d6e;
        }}
        
        .status-warning {{
            background: #fff8e1;
            color: #f39c12;
        }}
        
        .status-danger {{
            background: #ffebee;
            color: #c62828;
        }}
        
        .number-badge {{
            background: #f0f0f0;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 600;
            color: #333;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: white;
            font-size: 13px;
        }}

        .scan-btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 22px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s, opacity 0.2s;
            margin-top: 12px;
        }}
        .scan-btn:hover:not(:disabled) {{
            background: #5a6fd6;
        }}
        .scan-btn:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
        }}
        .scan-btn.running {{
            background: #f39c12;
        }}

        .refresh-info {{
            background: rgba(255, 255, 255, 0.1);
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
            font-size: 13px;
        }}
        
        @media (max-width: 768px) {{
            table {{
                font-size: 12px;
            }}
            
            th, td {{
                padding: 10px 15px;
            }}
            
            .stat-card .value {{
                font-size: 28px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="refresh-info">
            🔄 Page auto-refreshes every 30 seconds | Update cycle: {update_interval}s
        </div>
        
        <header>
            <h1>🔄 System Update Report</h1>
            <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <button id="scanBtn" class="scan-btn">Scan Now</button>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Hosts</h3>
                <div class="value">{stats["total_hosts"]}</div>
            </div>
            <div class="stat-card">
                <h3>Updates Applied</h3>
                <div class="value">{stats["total_updates"]}</div>
            </div>
            <div class="stat-card">
                <h3>Security Updates</h3>
                <div class="value">{stats["total_security"]}</div>
            </div>
            <div class="stat-card">
                <h3>Reboot Required</h3>
                <div class="value">{stats["hosts_needing_reboot"]}</div>
            </div>
        </div>
        
        <div class="hosts-table">
            <div class="table-header">
                <h2>Host Details</h2>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Hostname</th>
                        <th>OS</th>
                        <th>IP Address</th>
                        <th>Updates</th>
                        <th>Security</th>
                        <th>Reboot</th>
                        <th>Status</th>
                        <th>Last Update</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>Automated System Update Monitor</p>
        </div>
    </div>

    <script>
        // Auto-refresh page every 30 seconds
        setTimeout(function() {{ location.reload(); }}, 30000);

        const btn = document.getElementById('scanBtn');
        let pollInterval = null;
        let wasActive = false;

        function setScanState(state) {{
            if (state === 'idle') {{
                btn.textContent = 'Scan Now';
                btn.disabled = false;
                btn.classList.remove('running');
            }} else if (state === 'queued') {{
                btn.textContent = 'Queued...';
                btn.disabled = true;
                btn.classList.add('running');
            }} else if (state === 'running') {{
                btn.textContent = 'Scanning...';
                btn.disabled = true;
                btn.classList.add('running');
            }}
        }}

        function pollStatus() {{
            fetch('/api/scan/status')
                .then(r => r.json())
                .then(data => {{
                    if (data.running) {{
                        wasActive = true;
                        setScanState('running');
                    }} else if (data.queued) {{
                        wasActive = true;
                        setScanState('queued');
                    }} else {{
                        setScanState('idle');
                        clearInterval(pollInterval);
                        pollInterval = null;
                        if (wasActive) {{
                            wasActive = false;
                            location.reload();
                        }}
                    }}
                }});
        }}

        btn.addEventListener('click', function() {{
            wasActive = true;
            setScanState('queued');
            fetch('/api/scan', {{ method: 'POST' }})
                .then(r => {{
                    if (r.status === 409) {{ setScanState('running'); }}
                    if (!pollInterval) {{
                        pollInterval = setInterval(pollStatus, 3000);
                    }}
                }})
                .catch(() => {{ wasActive = false; setScanState('idle'); }});
        }});

        // Pick up in-progress state on page load without triggering a reload
        pollStatus();
    </script>
</body>
</html>"""
    
    return html

@app.route('/api/results')
def api_results():
    """API endpoint to get JSON results"""
    results = load_results()
    return jsonify(results)

@app.route('/api/stats')
def api_stats():
    """API endpoint to get statistics"""
    results = load_results()
    
    stats = {
        "total_hosts": len(results),
        "total_updates": sum(r.get("updates_installed", 0) for r in results),
        "total_security": sum(r.get("security_updates", 0) for r in results),
        "hosts_needing_reboot": sum(1 for r in results if r.get("reboot_required", False)),
        "last_updated": datetime.now().isoformat()
    }
    
    return jsonify(stats)

@app.route('/api/scan', methods=['POST'])
def trigger_scan():
    """Trigger a manual scan cycle"""
    if os.path.exists(LOCK_FILE):
        return jsonify({"status": "already_running"}), 409
    Path(TRIGGER_FILE).touch()
    return jsonify({"status": "triggered"}), 202

@app.route('/api/scan/status')
def scan_status():
    """Return whether a scan is currently running"""
    return jsonify({
        "running": os.path.exists(LOCK_FILE),
        "queued": os.path.exists(TRIGGER_FILE),
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    print("Starting Flask web server on 0.0.0.0:8080")
    app.run(host='0.0.0.0', port=8080, debug=False)

#!/usr/bin/env python3

import json
import sys
import os
from datetime import datetime
from pathlib import Path
import glob

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
            print(f"Error loading {json_file}: {e}", file=sys.stderr)
    
    return results

def calculate_stats(results):
    """Calculate aggregate statistics"""
    if not results:
        return {
            "total_hosts": 0,
            "total_updates": 0,
            "total_security": 0,
            "hosts_needing_reboot": 0
        }
    
    return {
        "total_hosts": len(results),
        "total_updates": sum(r.get("updates_installed", 0) for r in results),
        "total_security": sum(r.get("security_updates", 0) for r in results),
        "hosts_needing_reboot": sum(1 for r in results if r.get("reboot_required", False))
    }

def get_status_color(host_data):
    """Determine color based on host status"""
    if host_data.get("reboot_required"):
        return "#ff6b6b"  # Red
    elif host_data.get("updates_installed", 0) > 0:
        return "#ffd93d"  # Yellow
    else:
        return "#6bcf7f"  # Green

def generate_html(results, stats):
    """Generate HTML report"""
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Update Report</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 30px;
        }
        
        header h1 {
            color: #333;
            margin-bottom: 10px;
        }
        
        header p {
            color: #666;
            font-size: 14px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            text-align: center;
        }
        
        .stat-card h3 {
            color: #666;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }
        
        .stat-card .value {
            font-size: 36px;
            font-weight: bold;
            color: #667eea;
        }
        
        .hosts-table {
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }
        
        .table-header {
            background: #f8f9fa;
            padding: 20px 30px;
            border-bottom: 1px solid #e9ecef;
        }
        
        .table-header h2 {
            color: #333;
            font-size: 18px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        thead {
            background: #f8f9fa;
        }
        
        th {
            padding: 15px 30px;
            text-align: left;
            font-weight: 600;
            color: #666;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid #e9ecef;
        }
        
        td {
            padding: 15px 30px;
            border-bottom: 1px solid #e9ecef;
            color: #555;
        }
        
        tbody tr:hover {
            background: #f8f9fa;
        }
        
        .status-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .status-success {
            background: #e8f9f0;
            color: #1a9d6e;
        }
        
        .status-warning {
            background: #fff8e1;
            color: #f39c12;
        }
        
        .status-danger {
            background: #ffebee;
            color: #c62828;
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            vertical-align: middle;
        }
        
        .number-badge {
            background: #f0f0f0;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 600;
            color: #333;
        }
        
        .footer {
            text-align: center;
            margin-top: 30px;
            color: white;
            font-size: 13px;
        }
        
        @media (max-width: 768px) {
            table {
                font-size: 12px;
            }
            
            th, td {
                padding: 10px 15px;
            }
            
            .stat-card .value {
                font-size: 28px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔄 System Update Report</h1>
            <p>Last updated: {last_updated}</p>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Hosts</h3>
                <div class="value">{total_hosts}</div>
            </div>
            <div class="stat-card">
                <h3>Updates Applied</h3>
                <div class="value">{total_updates}</div>
            </div>
            <div class="stat-card">
                <h3>Security Updates</h3>
                <div class="value">{total_security}</div>
            </div>
            <div class="stat-card">
                <h3>Reboot Required</h3>
                <div class="value">{hosts_needing_reboot}</div>
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
            <p>Automated System Update Monitor • Next scan in {update_interval} seconds</p>
        </div>
    </div>
</body>
</html>
"""
    
    # Generate table rows
    table_rows = ""
    for host in results:
        reboot_status = "Yes" if host.get("reboot_required") else "No"
        reboot_badge_class = "status-danger" if host.get("reboot_required") else "status-success"
        
        status_color = get_status_color(host)
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
    
    # Replace placeholders
    update_interval = os.environ.get("UPDATE_INTERVAL", "3600")
    html = html.replace("{last_updated}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    html = html.replace("{total_hosts}", str(stats["total_hosts"]))
    html = html.replace("{total_updates}", str(stats["total_updates"]))
    html = html.replace("{total_security}", str(stats["total_security"]))
    html = html.replace("{hosts_needing_reboot}", str(stats["hosts_needing_reboot"]))
    html = html.replace("{table_rows}", table_rows)
    html = html.replace("{update_interval}", update_interval)
    
    return html

def main():
    if len(sys.argv) > 1:
        result_file = sys.argv[1]
        if os.path.exists(result_file):
            print(f"Processing result file: {result_file}", file=sys.stderr)
    
    # Load all results
    results = load_results()
    stats = calculate_stats(results)
    
    # Generate HTML
    html_content = generate_html(results, stats)
    
    # Write to index.html
    output_file = os.path.join(REPORTS_DIR, "index.html")
    with open(output_file, 'w') as f:
        f.write(html_content)
    
    print(f"Report generated: {output_file}", file=sys.stderr)

if __name__ == "__main__":
    main()

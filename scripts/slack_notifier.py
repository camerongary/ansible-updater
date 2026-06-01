#!/usr/bin/env python3

import json
import sys
import os
import glob
from datetime import datetime
import requests

REPORTS_DIR = "/reports"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

def load_latest_results():
    """Load the most recent update results"""
    json_files = glob.glob(os.path.join(REPORTS_DIR, "*_update_result.json"))
    
    if not json_files:
        return []
    
    results = []
    for json_file in sorted(json_files, reverse=True)[:10]:  # Get last 10
        try:
            with open(json_file, 'r') as f:
                results.append(json.load(f))
        except Exception as e:
            print(f"Error loading {json_file}: {e}", file=sys.stderr)
    
    return results

def build_slack_message(results):
    """Build a Slack message from results"""
    
    if not results:
        return {
            "text": "System Update Report",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":warning: No systems have been scanned yet"
                    }
                }
            ]
        }
    
    # Calculate stats
    total_updates = sum(r.get("updates_installed", 0) for r in results)
    total_security = sum(r.get("security_updates", 0) for r in results)
    reboot_needed = sum(1 for r in results if r.get("reboot_required", False))
    
    # Determine emoji based on status
    if reboot_needed > 0:
        emoji = ":rotating_light:"
    elif total_updates > 0:
        emoji = ":zap:"
    else:
        emoji = ":white_check_mark:"
    
    # Build host fields
    host_fields = []
    for host in sorted(results, key=lambda x: x.get("updates_installed", 0), reverse=True):
        hostname = host.get("hostname", "Unknown")
        updates = host.get("updates_installed", 0)
        security = host.get("security_updates", 0)
        reboot = ":warning:" if host.get("reboot_required") else ":white_check_mark:"
        
        status = f"{hostname}\n"
        status += f"Updates: {updates} | Security: {security}\n"
        status += f"Reboot: {reboot}"
        
        host_fields.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": status
            }
        })
    
    # Build main message
    message = {
        "text": "System Update Report",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} System Update Report"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Hosts Scanned*\n{len(results)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Updates*\n{total_updates}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Security Updates*\n{total_security}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Reboot Needed*\n{reboot_needed}"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]
    }
    
    # Add host details
    message["blocks"].extend(host_fields[:5])  # Limit to first 5 hosts to avoid message size issues
    
    if len(results) > 5:
        message["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"_And {len(results) - 5} more hosts..._"
            }
        })
    
    # Add footer
    message["blocks"].append({
        "type": "divider"
    })
    message["blocks"].append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"<http://localhost|View Full Report> • Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        }
    })
    
    return message

def send_to_slack(message):
    """Send message to Slack webhook"""
    
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not set, skipping Slack notification", file=sys.stderr)
        return False
    
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=message,
            timeout=10
        )
        
        if response.status_code == 200:
            print("Slack notification sent successfully", file=sys.stderr)
            return True
        else:
            print(f"Slack webhook returned {response.status_code}: {response.text}", file=sys.stderr)
            return False
            
    except Exception as e:
        print(f"Error sending Slack notification: {e}", file=sys.stderr)
        return False

def main():
    # Load results
    results = load_latest_results()
    
    # Build and send message
    message = build_slack_message(results)
    send_to_slack(message)

if __name__ == "__main__":
    main()

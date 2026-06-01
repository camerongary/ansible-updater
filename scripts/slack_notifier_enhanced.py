#!/usr/bin/env python3

"""
Enhanced Slack Notifier for Ansible Update Manager
Sends beautiful formatted update reports to Slack
"""

import json
import sys
import os
import glob
from datetime import datetime
import requests

REPORTS_DIR = "/reports"

# Get webhook from environment or use default
SLACK_WEBHOOK_URL = os.environ.get(
    "SLACK_WEBHOOK_URL",
    "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
)

def load_latest_results():
    """Load the most recent update results"""
    json_files = glob.glob(os.path.join(REPORTS_DIR, "*_update_result.json"))
    
    if not json_files:
        return []
    
    results = []
    for json_file in sorted(json_files, reverse=True)[:15]:  # Get last 15
        try:
            with open(json_file, 'r') as f:
                results.append(json.load(f))
        except Exception as e:
            print(f"Error loading {json_file}: {e}", file=sys.stderr)
    
    return results

def get_status_emoji(host):
    """Get emoji based on host status"""
    if host.get("reboot_required"):
        return "🔴"  # Red - reboot needed
    elif host.get("updates_installed", 0) > 0:
        return "🟡"  # Yellow - updates applied
    else:
        return "🟢"  # Green - up to date

def build_slack_message(results):
    """Build a beautiful Slack message from results"""
    
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
    
    # Determine overall emoji based on status
    if reboot_needed > 0:
        emoji = ":rotating_light:"
        color_indicator = "⚠️"
    elif total_updates > 0:
        emoji = ":zap:"
        color_indicator = "🔄"
    else:
        emoji = ":white_check_mark:"
        color_indicator = "✅"
    
    # Build blocks
    blocks = [
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
    
    # Add host details (max 6 to avoid message size limits)
    host_count = 0
    for host in sorted(results, key=lambda x: x.get("updates_installed", 0), reverse=True):
        if host_count >= 6:
            break
        
        hostname = host.get("hostname", "Unknown")
        os_name = host.get("os_name", "Unknown")
        updates = host.get("updates_installed", 0)
        security = host.get("security_updates", 0)
        reboot = "⚠️ YES" if host.get("reboot_required") else "✅ NO"
        status_emoji = get_status_emoji(host)
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{status_emoji} *{hostname}*\n"
                       f"OS: {os_name}\n"
                       f"Updates: {updates} | Security: {security} | Reboot: {reboot}"
            }
        })
        
        host_count += 1
    
    # Show if there are more hosts
    if len(results) > 6:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"_And {len(results) - 6} more hosts..._"
            }
        })
    
    # Add footer with link and timestamp
    blocks.append({
        "type": "divider"
    })
    
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"<http://localhost|View Full Dashboard> • Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        }
    })
    
    return {
        "text": "System Update Report",
        "blocks": blocks
    }

def build_summary_message(results):
    """Build a concise summary message"""
    
    if not results:
        message = "No systems scanned yet"
    else:
        total_updates = sum(r.get("updates_installed", 0) for r in results)
        reboot_needed = sum(1 for r in results if r.get("reboot_required", False))
        
        if reboot_needed > 0:
            message = f"⚠️ {len(results)} hosts scanned: {total_updates} updates available, {reboot_needed} need reboot"
        elif total_updates > 0:
            message = f"🔄 {len(results)} hosts scanned: {total_updates} updates applied"
        else:
            message = f"✅ {len(results)} hosts scanned: All systems up to date"
    
    return {
        "text": message
    }

def send_to_slack(message, message_type="detailed"):
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
            print(f"✅ Slack {message_type} message sent successfully", file=sys.stderr)
            return True
        else:
            print(f"❌ Slack webhook returned {response.status_code}: {response.text}", file=sys.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error sending to Slack: {e}", file=sys.stderr)
        return False

def main():
    # Load results
    results = load_latest_results()
    
    # Build and send detailed message
    detailed_message = build_slack_message(results)
    send_to_slack(detailed_message, "detailed")
    
    # Optionally also send a concise summary (commented out to avoid duplicate messages)
    # summary_message = build_summary_message(results)
    # send_to_slack(summary_message, "summary")
    
    print(f"✅ Slack notification processed for {len(results)} hosts", file=sys.stderr)

if __name__ == "__main__":
    main()

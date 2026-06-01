#!/usr/bin/env python3

"""
Slack Webhook Integration Test
Tests the Slack webhook URL and sends sample messages
"""

import requests
import json
import sys
from datetime import datetime

SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

def test_basic_message():
    """Test 1: Send a basic text message"""
    print("Test 1: Sending basic text message...")
    
    message = {
        "text": "🧪 Ansible Update Manager - Slack Webhook Test"
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=10)
        if response.status_code == 200:
            print("✓ Basic message sent successfully\n")
            return True
        else:
            print(f"✗ Failed with status {response.status_code}: {response.text}\n")
            return False
    except Exception as e:
        print(f"✗ Error: {e}\n")
        return False

def test_rich_message():
    """Test 2: Send a rich formatted message with blocks"""
    print("Test 2: Sending rich formatted message...")
    
    message = {
        "text": "System Update Report",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔄 System Update Report"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": "*Hosts Scanned*\n5"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Total Updates*\n23"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Security Updates*\n8"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Reboot Needed*\n2"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=10)
        if response.status_code == 200:
            print("✓ Rich formatted message sent successfully\n")
            return True
        else:
            print(f"✗ Failed with status {response.status_code}: {response.text}\n")
            return False
    except Exception as e:
        print(f"✗ Error: {e}\n")
        return False

def test_alert_message():
    """Test 3: Send an alert message"""
    print("Test 3: Sending alert message...")
    
    message = {
        "text": "⚠️ Updates Available",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "⚠️ *Many Updates Available*\n\n:warning: 45 updates pending across 10 hosts\n:warning: 12 security updates available\n:warning: 3 hosts need reboot"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Dashboard"
                        },
                        "url": "http://localhost",
                        "style": "primary"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=10)
        if response.status_code == 200:
            print("✓ Alert message sent successfully\n")
            return True
        else:
            print(f"✗ Failed with status {response.status_code}: {response.text}\n")
            return False
    except Exception as e:
        print(f"✗ Error: {e}\n")
        return False

def test_host_details_message():
    """Test 4: Send host details message"""
    print("Test 4: Sending host details message...")
    
    message = {
        "text": "Update Details by Host",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Update Details by Host*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "🖥️ *web-server-1*\nOS: Ubuntu 22.04\nUpdates: 5 | Security: 2 | Reboot: :white_check_mark:"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "🖥️ *db-server-1*\nOS: CentOS 8\nUpdates: 12 | Security: 4 | Reboot: :warning:"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "🖥️ *app-server-2*\nOS: Debian 11\nUpdates: 0 | Security: 0 | Reboot: :white_check_mark:"
                }
            }
        ]
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=10)
        if response.status_code == 200:
            print("✓ Host details message sent successfully\n")
            return True
        else:
            print(f"✗ Failed with status {response.status_code}: {response.text}\n")
            return False
    except Exception as e:
        print(f"✗ Error: {e}\n")
        return False

def test_success_message():
    """Test 5: Send success notification"""
    print("Test 5: Sending success notification...")
    
    message = {
        "text": "✅ All Systems Updated",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "✅ *Update Cycle Completed Successfully*\n\nTime: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\nStatus: All systems up to date"
                }
            }
        ]
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=10)
        if response.status_code == 200:
            print("✓ Success message sent successfully\n")
            return True
        else:
            print(f"✗ Failed with status {response.status_code}: {response.text}\n")
            return False
    except Exception as e:
        print(f"✗ Error: {e}\n")
        return False

def main():
    print("=" * 60)
    print("Slack Webhook Integration Test")
    print("=" * 60)
    print()
    print(f"Webhook URL: {SLACK_WEBHOOK_URL[:50]}...")
    print()
    
    results = {
        "Basic Message": test_basic_message(),
        "Rich Formatted": test_rich_message(),
        "Alert Message": test_alert_message(),
        "Host Details": test_host_details_message(),
        "Success Message": test_success_message()
    }
    
    print("=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All Slack integration tests passed!")
        print("\nYour webhook is working correctly and ready for production.")
        print("\nCheck your Slack workspace for the test messages.")
        return 0
    else:
        print("\n⚠️ Some tests failed. Check the webhook URL and try again.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

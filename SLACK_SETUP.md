# Slack Integration Setup & Testing Guide

## ✅ Your Slack Webhook is Configured!

**Workspace**: T0ALY7FCQ6P
**Webhook URL**: `https://hooks.slack.com/services/YOUR/WEBHOOK/URL`

---

## 🔔 What Will Be Posted to Slack

The Ansible Update Manager will send automatic notifications after each update cycle with:

### Message Types

#### 1. **Standard Update Report**
```
🔄 System Update Report
├─ Hosts Scanned: 5
├─ Total Updates: 23
├─ Security Updates: 8
└─ Reboot Required: 2
```

#### 2. **Per-Host Details**
```
🖥️ web-server-1
├─ OS: Ubuntu 22.04
├─ Updates: 5
├─ Security: 2
└─ Reboot: ✅

🖥️ db-server-1
├─ OS: CentOS 8
├─ Updates: 12
├─ Security: 4
└─ Reboot: ⚠️
```

#### 3. **Alert Messages** (When needed)
```
⚠️ Many Updates Available
├─ 45 updates pending across 10 hosts
├─ 12 security updates available
└─ 3 hosts need reboot
```

#### 4. **Success Messages**
```
✅ All Systems Updated
└─ All systems are up to date
```

---

## 🚀 Quick Start with Your Webhook

### Step 1: Use the Provided .env File

The `.env` file already has your webhook configured:

```bash
cat .env
```

Output:
```
NETWORK_RANGE=192.168.1.0/24
UPDATE_INTERVAL=3600
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Step 2: Start the Container

```bash
docker-compose up -d
```

### Step 3: Check Slack

Your first notification will appear after the first scan cycle (or after `UPDATE_INTERVAL` seconds).

### Step 4: View in Slack

Look for messages from "Ansible Update Manager" in your Slack workspace.

---

## 🧪 Testing Your Slack Integration

### Test Option 1: Using Python Script (Outside Docker)

```bash
python3 test_slack_webhook.py
```

This will send 5 different message types to verify integration.

### Test Option 2: Using Docker Container

```bash
docker-compose exec ansible-updater python3 /scripts/slack_notifier.py
```

This runs the actual notifier script inside the container.

### Test Option 3: Manual curl Test

```bash
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"🧪 Slack Webhook Test - Ansible Update Manager"}' \
  https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

---

## 📊 Example Slack Messages

### Message 1: After Successful Scan
```
🔄 System Update Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Hosts Scanned:     5
Total Updates:     23
Security Updates:  8
Reboot Required:   2

Last Updated: 2024-03-23 10:30:00
View Full Report: http://localhost
```

### Message 2: Host Details
```
🖥️ Host: web-server-1
    OS: Ubuntu 22.04
    Updates: 5 | Security: 2 | Reboot: ✅

🖥️ Host: db-server-1
    OS: CentOS 8
    Updates: 12 | Security: 4 | Reboot: ⚠️

🖥️ Host: app-server-2
    OS: Debian 11
    Updates: 0 | Security: 0 | Reboot: ✅
```

### Message 3: Alert (Many Updates)
```
⚠️ ALERT: Many Updates Available
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
45 updates pending across 10 hosts
12 security updates available
3 hosts need reboot

[View Dashboard]
```

### Message 4: Success (All Updated)
```
✅ All Systems Updated
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All systems are up to date!
Next scan: 2024-03-23 11:30:00
```

---

## 🎨 Slack Message Formatting

### Text Formatting Available
- `*bold*` → **bold**
- `_italic_` → _italic_
- `~strikethrough~` → ~~strikethrough~~
- `` `code` `` → `code`
- Emojis: ✅ ⚠️ 🔄 🖥️ etc.

### Message Structure
```json
{
  "text": "Summary for fallback",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Bold* and _italic_ with :emoji:"
      }
    }
  ]
}
```

---

## 📝 Customizing Slack Messages

Edit `scripts/slack_notifier.py` to customize:

1. **Message Format**: Change the blocks structure
2. **Include/Exclude Fields**: Add/remove from host details
3. **Color Coding**: Adjust based on thresholds
4. **Emoji Usage**: Choose your preferred emojis

### Example: Change Alert Threshold

In `scripts/slack_notifier.py`, line ~80:

```python
# Current: Alert if total_updates > threshold
if total_updates > 50:
    emoji = ":rotating_light:"
```

Change to:
```python
if total_updates > 100:  # Higher threshold
    emoji = ":rotating_light:"
```

---

## 🔍 Troubleshooting Slack Integration

### Issue 1: No Messages in Slack

**Check**:
1. Webhook URL is correct (compare with Slack app settings)
2. Container is running: `docker-compose ps`
3. First update cycle has completed: `docker-compose logs | grep "Slack"`

**Solution**:
```bash
# Force immediate test
docker-compose exec ansible-updater python3 /scripts/slack_notifier.py

# Check logs
docker-compose logs ansible-updater | tail -50
```

### Issue 2: Webhook URL Error

**Error message**:
```
Invalid Webhook URL
```

**Solution**:
1. Verify webhook in Slack: Settings → Apps → Incoming Webhooks
2. Copy exact URL from Slack
3. Update `.env` file
4. Restart: `docker-compose restart`

### Issue 3: Timeout

**Error message**:
```
Connection timeout to hooks.slack.com
```

**Causes**:
- Network firewall blocking Slack
- DNS resolution issues
- Temporary Slack outage

**Solution**:
```bash
# Test connectivity
curl -I https://hooks.slack.com

# Test from container
docker-compose exec ansible-updater curl -I https://hooks.slack.com
```

### Issue 4: Messages Too Large

**Error**:
```
Message too large for API
```

**Solution**: Reduce number of hosts in message or limit to top 5 hosts

---

## 📋 Environment Configuration

Your `.env` file is already set up. To modify:

```bash
# Edit configuration
nano .env

# Change update interval
UPDATE_INTERVAL=1800  # 30 minutes instead of 1 hour

# Add different network
NETWORK_RANGE=10.0.0.0/24

# Save and restart
docker-compose restart
```

---

## 🔐 Security Notes

⚠️ **Important**: Your webhook URL is sensitive!

- ✅ Keep it in `.env` (not in git)
- ✅ Add `.env` to `.gitignore`
- ✅ Don't share publicly
- ✅ Rotate if leaked
- ❌ Don't commit to version control

### Rotate Webhook (If Compromised)

1. Go to Slack Workspace → Settings → App Directory
2. Find "Incoming Webhooks"
3. Delete old webhook
4. Create new one
5. Update `.env` file
6. Restart container

---

## 📊 Slack Message Fields Explained

| Field | Description |
|-------|-------------|
| Hosts Scanned | Total unique hosts discovered |
| Total Updates | Sum of all updates across hosts |
| Security Updates | Critical/security-only updates |
| Reboot Required | Count of hosts needing restart |
| Last Scan Age | How long since last update cycle |

---

## 🎯 Integration Workflow

```
Update Cycle Completes
        ↓
Collect Statistics
        ↓
Generate Reports (HTML + API)
        ↓
Send to Slack
        ↓
Post Beautiful Message
        ↓
Team Sees Update Status
        ↓
Dashboard Accessible via Link
```

---

## 📞 Support

### Verify Your Webhook Works

1. Manual test:
```bash
python3 test_slack_webhook.py
```

2. Check Slack channel:
- Look for messages in the channel where webhook posts
- Default: #general or your chosen channel

3. View logs:
```bash
docker-compose logs ansible-updater | grep -i slack
```

### Get Webhook Channel Info

In Slack, click the webhook → View Details → Channel

---

## ✨ Advanced: Custom Slack Formatting

### Send Mentions
```python
"text": "<!here> Update cycle complete"
```

### Send User/Group Mentions
```python
"text": "<@U12345|username> Check updates"
"text": "<!subteam^S12345|@devops> Review needed"
```

### Add Buttons
```json
{
  "type": "actions",
  "elements": [
    {
      "type": "button",
      "text": {"type": "plain_text", "text": "View Dashboard"},
      "url": "http://your-server",
      "style": "primary"
    }
  ]
}
```

### Add Threads
```python
"thread_ts": "1234567890.123456"  # Reply in thread
```

---

## 🚀 Next Steps

1. ✅ **Webhook configured** → Already done!
2. ✅ **First message sent** → Check Slack workspace
3. 📊 **Monitor updates** → Via Slack + Dashboard
4. 🎨 **Customize messages** (optional) → Edit `slack_notifier.py`
5. 🔔 **Add team mentions** (optional) → Add to notify team

---

## 📚 References

- [Slack Incoming Webhooks Documentation](https://api.slack.com/messaging/webhooks)
- [Slack Block Kit (Message Formatting)](https://api.slack.com/block-kit)
- [Slack Message Format Guide](https://api.slack.com/messaging/composing)
- Our `slack_notifier.py` for implementation examples

---

**Your Slack integration is now fully configured and ready to use!** 🎉

Start your containers and you'll see update reports automatically posted to Slack after each scan cycle.

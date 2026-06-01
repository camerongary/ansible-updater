# copy-ssh-keys.sh - Step-by-Step Explanation

## Overview

`copy-ssh-keys.sh` is a fully automated SSH key distribution script that discovers all servers in your network and copies SSH keys to them.

---

## 7 Main Stages

### **STAGE 1: Setup & Configuration** (Lines 1-44)

**What happens:**
1. Script starts and sets up color codes for pretty output
2. Loads configuration:
   - `NETWORK_RANGE` = 192.168.12.0/24 (your network to scan)
   - `SSH_USER` = root (user to copy key for)
   - `SSH_KEY` = ~/.ssh/id_rsa (your SSH private key)
   - `SSH_KEY_PUB` = ~/.ssh/id_rsa.pub (your SSH public key)
   - `TIMEOUT` = 5 seconds (max wait for operations)
   - `RETRIES` = 3 (try 3 times before giving up)

**Output you see:**
- Banner showing network range and SSH user

**Can be customized by:**
```bash
bash copy-ssh-keys.sh 192.168.12.0/24 root ~/.ssh/id_rsa
```

---

### **STAGE 2: Check Prerequisites** (Lines 46-84)

**Purpose:** Verify everything needed is installed and available

**Checks performed:**

1. **SSH Private Key Exists** (lines 50-57)
   - Looks for `~/.ssh/id_rsa`
   - If not found, tells you to generate one:
     ```bash
     ssh-keygen -t ed25519 -f ~/.ssh/id_rsa -N ""
     ```
   - ✓ Prints: "SSH private key found"

2. **SSH Public Key Exists** (lines 59-65)
   - Looks for `~/.ssh/id_rsa.pub`
   - Public key is generated automatically with private key
   - ✓ Prints: "SSH public key found"

3. **nmap Is Installed** (lines 67-73)
   - Checks if `nmap` command exists
   - nmap will scan for live servers
   - If not installed, tells you to install:
     ```bash
     sudo apt-get install nmap
     ```
   - ✓ Prints: "nmap is installed"

4. **ssh-copy-id Is Available** (lines 75-81)
   - Checks if `ssh-copy-id` command exists
   - This tool copies SSH key to servers
   - If not installed, tells you to install:
     ```bash
     sudo apt-get install openssh-client
     ```
   - ✓ Prints: "ssh-copy-id is available"

**If anything fails:**
- Script exits immediately (stops)
- You must install missing tools before continuing

**Output example:**
```
════════════════════════════════════════════════════
Checking Prerequisites
════════════════════════════════════════════════════
✓ SSH private key found: /root/.ssh/id_rsa
✓ SSH public key found: /root/.ssh/id_rsa.pub
✓ nmap is installed
✓ ssh-copy-id is available
```

---

### **STAGE 3: User Confirmation** (Lines 278-291)

**What happens:**
- Script displays what it's about to do
- Asks for user confirmation before proceeding

**Information shown:**
```
SSH Key Distribution Tool

This tool will copy your SSH public key to all discovered servers
Network Range: 192.168.12.0/24
SSH User: root
SSH Key: ~/.ssh/id_rsa

Continue? (y/n)
```

**User action:**
- Type `y` and press Enter to continue
- Type `n` and press Enter to cancel

**Why it exists:**
- Safety measure - you must acknowledge what's happening
- Gives you chance to verify settings are correct

---

### **STAGE 4: Network Discovery** (Lines 86-115)

**Purpose:** Find all live servers in your network

**What it does:**

1. **Run nmap Scan** (line 93)
   ```bash
   nmap -sn 192.168.12.0/24 -oG -
   ```
   - `-sn` = ping scan (no port scan)
   - `192.168.12.0/24` = your network
   - `-oG -` = output in greppable format
   - This sends ping to every IP in the network

2. **Filter for Live Hosts** (line 93)
   ```bash
   grep "Up" | awk '{print $2}'
   ```
   - Keeps only hosts that responded to ping (status = "Up")
   - Extracts just the IP addresses

3. **Sort Results** (line 93)
   ```bash
   sort -V
   ```
   - Sorts IPs numerically (192.168.12.10 before 192.168.12.11)

4. **Convert to Array** (line 101)
   - Stores list of IPs in `SERVER_ARRAY`
   - Also creates `SERVERS_MAP` tracking array (initially all 0 = not processed)

**Output example:**
```
════════════════════════════════════════════════════
Discovering Servers in 192.168.12.0/24
════════════════════════════════════════════════════
ℹ Running nmap scan (this may take a minute)...
✓ Discovered 5 server(s):
  • 192.168.12.10
  • 192.168.12.11
  • 192.168.12.15
  • 192.168.12.20
  • 192.168.12.25
```

**Time:** Usually 30-90 seconds depending on network

**Behind the scenes:**
```
nmap -sn 192.168.12.0/24 output looks like:

Starting Nmap 7.80 ( https://nmap.org ) at 2024-03-23 10:30 UTC
Nmap scan report for 192.168.12.1
Host is up (0.001s latency).
Nmap scan report for 192.168.12.10
Host is up (0.005s latency).
[... more hosts ...]

Output in greppable format after filtering:
192.168.12.10
192.168.12.11
192.168.12.15
192.168.12.20
192.168.12.25
```

---

### **STAGE 5: Copy SSH Keys** (Lines 163-215)

**Purpose:** Copy SSH key to each discovered server

**For each server, it does:**

1. **Check if Key Already Works** (lines 176-181)
   ```bash
   ssh -o ConnectTimeout=3 -i "$SSH_KEY" "$SSH_USER@$ip" "echo ok"
   ```
   - Tries to SSH to server without password
   - If works, marks success and moves to next server
   - If fails, continues to try copying key

2. **Attempt Copy (up to 3 times)** (lines 185-196)
   ```bash
   ssh-copy-id -i "$SSH_KEY" "$SSH_USER@$ip"
   ```
   - First attempt: Try automatic copy
   - If fails: Wait 2 seconds
   - Second attempt: Try again
   - If fails: Wait 2 seconds  
   - Third attempt: Final try
   - If still fails: Move to interactive mode

3. **Interactive Fallback** (lines 199-210)
   - If 3 attempts fail, asks you:
     ```
     Would you like to try interactive copy for 192.168.12.10? (y/n)
     ```
   - If you say yes, runs ssh-copy-id interactively
   - It will ask for the password of that server
   - You type password and key gets copied

**Output example:**
```
════════════════════════════════════════════════════
Copying SSH Keys to All Servers
════════════════════════════════════════════════════

ℹ Processing 192.168.12.10...
✓ SSH key copied to 192.168.12.10

ℹ Processing 192.168.12.11...
ℹ Copying SSH key to 192.168.12.11 (attempt 1/3)...
⚠ Retry in 2 seconds...
ℹ Copying SSH key to 192.168.12.11 (attempt 2/3)...
✓ SSH key copied to 192.168.12.11

ℹ Processing 192.168.12.15...
✓ SSH key already works on 192.168.12.15 (no action needed)
```

---

### **STAGE 6: Verify SSH Access** (Lines 217-241)

**Purpose:** Test that SSH works on all servers after copying keys

**What it does:**

1. **Test Each Successful Server** (lines 224-234)
   - For each server marked as successful in SERVERS_MAP
   - Runs: `ssh -i ~/.ssh/id_rsa root@IP "echo ok"`
   - If works: Prints "✓ SSH access verified: 192.168.12.10"
   - If fails: Prints "✗ SSH access verification failed: 192.168.12.10"

2. **Count Results** (lines 237-239)
   - Counts how many verified vs failed
   - Shows summary

**Output example:**
```
════════════════════════════════════════════════════
Verifying SSH Access
════════════════════════════════════════════════════
✓ SSH access verified: 192.168.12.10
✓ SSH access verified: 192.168.12.11
✓ SSH access verified: 192.168.12.15
✓ SSH access verified: 192.168.12.20
✓ SSH access verified: 192.168.12.25

Verification complete:
  • Verified: 5
  • Failed: 0
```

---

### **STAGE 7: Final Summary Report** (Lines 243-267)

**Purpose:** Show final status and next steps

**What it displays:**

1. **Configuration Used** (lines 247-249)
   ```
   Network Range:     192.168.12.0/24
   SSH User:          root
   SSH Key:           ~/.ssh/id_rsa
   ```

2. **Status for Each Server** (lines 253-259)
   ```
   Status:
     ✓ 192.168.12.10
     ✓ 192.168.12.11
     ✓ 192.168.12.15
     ✗ 192.168.12.20    (if failed)
     ✓ 192.168.12.25
   ```

3. **Next Steps** (lines 262-265)
   ```
   ℹ Next steps:
     1. Test with: ssh -i ~/.ssh/id_rsa root@<ip>
     2. Deploy with: docker-compose up -d
     3. Monitor with: docker-compose logs -f
   ```

**Example output:**
```
════════════════════════════════════════════════════
Summary Report
════════════════════════════════════════════════════
Network Range:     192.168.12.0/24
SSH User:          root
SSH Key:           ~/.ssh/id_rsa

Status:
  ✓ 192.168.12.10
  ✓ 192.168.12.11
  ✓ 192.168.12.15
  ✓ 192.168.12.20
  ✓ 192.168.12.25

ℹ Next steps:
  1. Test with: ssh -i ~/.ssh/id_rsa root@<ip>
  2. Deploy with: docker-compose up -d
  3. Monitor with: docker-compose logs -f
```

---

## Complete Flow Diagram

```
START
  ↓
[Stage 1] Setup & Load Configuration
  ↓
[Stage 2] Check Prerequisites
  ├─ SSH key exists?
  ├─ nmap installed?
  ├─ ssh-copy-id available?
  └─ If any missing → EXIT
  ↓
[Stage 3] User Confirmation
  ├─ Show settings
  ├─ Ask "Continue?"
  └─ If user says no → EXIT
  ↓
[Stage 4] Network Discovery with nmap
  ├─ Run: nmap -sn 192.168.12.0/24
  ├─ Find all "Up" hosts
  ├─ Extract IP addresses
  └─ Sort and store
  ↓
[Stage 5] Copy Keys to All Servers
  ├─ For each discovered server:
  │  ├─ Test if key already works
  │  │  └─ If yes → Mark success, continue
  │  ├─ Try ssh-copy-id (attempt 1)
  │  │  └─ If fails → Try attempt 2
  │  ├─ Try ssh-copy-id (attempt 2)
  │  │  └─ If fails → Try attempt 3
  │  ├─ Try ssh-copy-id (attempt 3)
  │  │  └─ If fails → Ask for interactive copy
  │  ├─ If interactive selected
  │  │  └─ Prompt for password and try
  │  └─ Record result (success/fail)
  ↓
[Stage 6] Verify SSH Access
  ├─ For each successful server
  ├─ Run: ssh -i key root@ip "echo ok"
  ├─ Count verified vs failed
  └─ Display results
  ↓
[Stage 7] Final Summary Report
  ├─ Show configuration used
  ├─ Show per-server status
  ├─ Show next steps
  └─ Exit with success
  ↓
END
```

---

## Key Features Explained

### **Retry Logic**
The script tries 3 times before giving up:
1. First attempt - automatic
2. 2 second wait
3. Second attempt - automatic
4. 2 second wait
5. Third attempt - automatic
6. If all fail - ask for interactive mode

Why? Sometimes SSH needs a few seconds to accept connections.

### **Interactive Fallback**
If automatic copy fails, it asks you:
```
Would you like to try interactive copy for 192.168.12.10? (y/n)
```

This runs:
```bash
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.10
```

And prompts you for the server's password. You type it, and the key gets copied.

### **Verification**
After copying, it tests each server with:
```bash
ssh -i ~/.ssh/id_rsa root@192.168.12.10 "echo ok"
```

This ensures SSH works without password before considering it successful.

### **Pre-flight Checks**
Before doing anything, it verifies:
- Your SSH private key exists
- Your SSH public key exists
- nmap is installed (to scan network)
- ssh-copy-id is installed (to copy keys)

If any are missing, it stops and tells you how to fix it.

---

## Typical Execution Time

| Stage | Time |
|-------|------|
| Stage 1: Setup | < 1 second |
| Stage 2: Prerequisites | < 1 second |
| Stage 3: Confirmation | Waits for you |
| Stage 4: Network discovery | 30-90 seconds |
| Stage 5: Copy keys | 10-30 seconds |
| Stage 6: Verification | 5-10 seconds |
| Stage 7: Summary | < 1 second |
| **TOTAL** | **~1-2 minutes** |

---

## What Happens Behind the Scenes

### Network Discovery:
```bash
# What nmap scan looks like
$ nmap -sn 192.168.12.0/24
Starting Nmap...
Nmap scan report for 192.168.12.1
Host is up (0.001s latency).
Nmap scan report for 192.168.12.10
Host is up (0.005s latency).
...

# Script filters this to get just IPs:
192.168.12.1
192.168.12.10
192.168.12.11
...
```

### SSH Key Copy:
```bash
# What ssh-copy-id does
$ ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.10

# It essentially:
1. Reads your public key (~/.ssh/id_rsa.pub)
2. SSHes to the remote server
3. Appends your public key to ~/.ssh/authorized_keys on that server
4. Done! Now SSH works without password
```

### Verification:
```bash
# Tests SSH without password
$ ssh -i ~/.ssh/id_rsa root@192.168.12.10 "echo ok"
ok

# If works, SSH is configured correctly
```

---

## Troubleshooting What Each Stage Does

### If Stage 2 fails:
```
✗ SSH private key not found
```
→ Generate SSH key: `ssh-keygen -t ed25519 -f ~/.ssh/id_rsa -N ""`

### If Stage 4 fails:
```
ℹ Running nmap scan
✗ No servers discovered
```
→ Network unreachable or no servers online
→ Test: `nmap -sn 192.168.12.0/24` manually
→ Check: `ping 192.168.12.1` (gateway)

### If Stage 5 shows failures:
```
⚠ Could not copy SSH key to 192.168.12.10 automatically
Would you like to try interactive copy? (y/n)
```
→ Say `y` and type the server's password
→ Or check if SSH is running on target: `systemctl status ssh`

### If Stage 6 shows failures:
```
✗ SSH access verification failed: 192.168.12.10
```
→ SSH key wasn't actually copied
→ Test manually: `ssh root@192.168.12.10`
→ If asks for password, key didn't copy correctly

---

## Summary

The script's main job is simple:
1. **Check** you have everything needed
2. **Find** all servers in the network
3. **Copy** your SSH key to each one
4. **Verify** it works
5. **Report** the results

It's intelligent enough to:
- Retry failed copies
- Fall back to interactive mode
- Check if keys already work
- Verify everything at the end
- Give you helpful error messages

This makes it easy and automatic to set up SSH key authentication across your entire server infrastructure!

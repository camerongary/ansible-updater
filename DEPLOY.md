# Deploying / updating on the Docker host

The app runs on the Docker host (**192.168.12.30**) at
`/home/cameron/homelab-compose/ansible-updater`, as part of the
`camerongary/homelab-compose` repo. The live `.env` and the `reports/` data are
git-ignored, so they survive updates.

## Update workflow (git pull on host)

```bash
ssh cameron@192.168.12.30
cd /home/cameron/homelab-compose
git pull
cd ansible-updater
docker compose build
docker compose up -d
docker compose logs -f          # watch it start the dashboard, poller, check cycle
```

The dashboard is at **http://192.168.12.30:8080**.

## Notes

- `.env` (Slack webhook, `BOOTSTRAP_PASSWORD`) and `reports/` are git-ignored —
  never committed. Edit `.env` directly on the host.
- `REQUIRE_APPROVAL=true` (default) keeps the system in check-only mode: it lists
  available updates but installs nothing until you approve in the dashboard.
- `DASHBOARD_URL` / `TZ` are set in `.env` / `docker-compose.yml`.
- Backups of the directory are created as `~/ansible-updater-backup-<ts>.tar.gz`
  before manual pushes.

## Rolling back

```bash
cd /home/cameron/homelab-compose
git log --oneline -5            # find the previous good commit
git revert <commit>             # or: git checkout <commit> -- ansible-updater
cd ansible-updater && docker compose build && docker compose up -d
```

## Onboarding a new host

New VMs are discovered automatically. A host is added to the inventory once it's
reachable by the `cameron` SSH key AND has passwordless sudo. The auto-bootstrap
(`BOOTSTRAP_PASSWORD`) handles hosts where root SSH works or sudo is already
installed.

For a **minimal host with no `sudo` and root SSH disabled**, the updater logs
`ACTION REQUIRED` and skips it. Onboard it once, on the VM''s console (or `su -`
from a `cameron` SSH session):

```bash
# Run as the cameron user (prompts for cameron's password):
echo 'cameron ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/ansible-cameron
sudo chmod 440 /etc/sudoers.d/ansible-cameron

# If sudo isn't installed yet, first become root and install it:
#   su -   (then: apt-get install -y sudo || dnf install -y sudo ; exit)
```

The next scan (or "Scan Now") will then include it. To deliberately skip a host,
add its IP to `ansible/exclude_hosts.txt`.

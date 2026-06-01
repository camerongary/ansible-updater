# Docker Deployment Guide

## Local Development Setup

### Prerequisites
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group (optional, allows running without sudo)
sudo usermod -aG docker $USER
newgrp docker
```

### Quick Start
```bash
cd ansible-updater
cp .env.example .env
docker-compose up -d
```

## Production Deployment

### Pre-Deployment Checklist

- [ ] Docker and Docker Compose installed
- [ ] SSH keys configured for target servers
- [ ] Network connectivity verified
- [ ] Slack webhook URL obtained (if using notifications)
- [ ] Adequate storage for reports
- [ ] Firewall rules configured (port 80, optionally 8080)

### Deployment Steps

```bash
# 1. Clone/setup project
git clone <repo> ansible-updater
cd ansible-updater

# 2. Configure environment
cp .env.example .env
nano .env

# 3. Setup SSH
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.1.10
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.1.20
# ... repeat for all target servers

# 4. Build and deploy
docker-compose build
docker-compose up -d

# 5. Verify
make health

# 6. View dashboard
open http://localhost
```

## Docker Compose Variations

### Minimal Setup (Single Container)

```yaml
version: '3.8'
services:
  ansible-updater:
    build: .
    environment:
      - NETWORK_RANGE=192.168.1.0/24
      - UPDATE_INTERVAL=3600
    volumes:
      - ./reports:/reports
      - ~/.ssh:/root/.ssh:ro
    ports:
      - "80:8080"
```

### Production Setup (with persistent volumes)

```yaml
version: '3.8'
services:
  ansible-updater:
    build: .
    container_name: ansible-updater-prod
    environment:
      - NETWORK_RANGE=10.0.0.0/16
      - UPDATE_INTERVAL=3600
      - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
    volumes:
      - ansible-reports:/reports
      - ansible-ssh:/root/.ssh:ro
      - ansible-logs:/var/log/ansible
    restart: always
    networks:
      - ansible-network

volumes:
  ansible-reports:
    driver: local
  ansible-ssh:
    driver: local
  ansible-logs:
    driver: local

networks:
  ansible-network:
    driver: bridge
```

### High Availability Setup

```yaml
version: '3.8'
services:
  ansible-updater-1:
    build: .
    environment:
      - INSTANCE=primary
      - NETWORK_RANGE=192.168.1.0/24
    volumes:
      - shared-reports:/reports
    restart: always

  ansible-updater-2:
    build: .
    environment:
      - INSTANCE=secondary
      - NETWORK_RANGE=10.0.0.0/24
    volumes:
      - shared-reports:/reports
    restart: always

  nginx:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - shared-reports:/usr/share/nginx/html:ro
    restart: always

volumes:
  shared-reports:
    driver: local
```

## Container Registry Deployment

### Build and Push to Registry

```bash
# Build image
docker build -t your-registry/ansible-updater:latest .

# Login to registry
docker login your-registry

# Push image
docker push your-registry/ansible-updater:latest

# Pull and run
docker run -d \
  -e NETWORK_RANGE=192.168.1.0/24 \
  -e UPDATE_INTERVAL=3600 \
  -v ~/.ssh:/root/.ssh:ro \
  -v ansible-reports:/reports \
  -p 80:8080 \
  your-registry/ansible-updater:latest
```

## Kubernetes Deployment

### Helm Chart Values

```yaml
# values.yaml
replicaCount: 1

image:
  repository: your-registry/ansible-updater
  tag: latest
  pullPolicy: IfNotPresent

environment:
  NETWORK_RANGE: "192.168.1.0/24"
  UPDATE_INTERVAL: "3600"
  SLACK_WEBHOOK_URL: ""

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi

persistence:
  enabled: true
  storageClass: "standard"
  size: 10Gi

service:
  type: LoadBalancer
  port: 80
  targetPort: 8080

scheduler:
  enabled: true
  expression: "0 */1 * * *"  # Every hour
```

### Kubernetes Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ansible-updater
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ansible-updater
  template:
    metadata:
      labels:
        app: ansible-updater
    spec:
      containers:
      - name: ansible-updater
        image: your-registry/ansible-updater:latest
        env:
        - name: NETWORK_RANGE
          value: "192.168.1.0/24"
        - name: UPDATE_INTERVAL
          value: "3600"
        ports:
        - containerPort: 8080
        volumeMounts:
        - name: reports
          mountPath: /reports
        - name: ssh-key
          mountPath: /root/.ssh
          readOnly: true
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: reports
        persistentVolumeClaim:
          claimName: ansible-reports-pvc
      - name: ssh-key
        secret:
          secretName: ansible-ssh-key
          defaultMode: 0600

---
apiVersion: v1
kind: Service
metadata:
  name: ansible-updater
spec:
  selector:
    app: ansible-updater
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer
```

## Docker Swarm Deployment

```bash
# Initialize swarm
docker swarm init

# Create secret for SSH key
docker secret create ssh-key ~/.ssh/id_rsa

# Create service
docker service create \
  --name ansible-updater \
  --replicas 1 \
  -e NETWORK_RANGE=192.168.1.0/24 \
  -e UPDATE_INTERVAL=3600 \
  -p 80:8080 \
  --mount type=volume,source=ansible-reports,target=/reports \
  your-registry/ansible-updater:latest

# Check status
docker service ls
docker service logs ansible-updater
```

## Environment-Specific Configs

### Development

```bash
# .env.dev
NETWORK_RANGE=192.168.1.0/24
UPDATE_INTERVAL=300        # 5 minutes
SLACK_WEBHOOK_URL=
ANSIBLE_VERBOSITY=3
```

### Staging

```bash
# .env.staging
NETWORK_RANGE=10.0.1.0/24
UPDATE_INTERVAL=1800       # 30 minutes
SLACK_WEBHOOK_URL=https://...
ANSIBLE_VERBOSITY=1
```

### Production

```bash
# .env.prod
NETWORK_RANGE=10.0.0.0/16
UPDATE_INTERVAL=3600       # 1 hour
SLACK_WEBHOOK_URL=https://...
ANSIBLE_VERBOSITY=0
```

## Security Best Practices

### 1. Container Security
```bash
# Run as non-root
docker run --user 1000:1000 ...

# Use read-only filesystem
docker run --read-only ...

# Drop capabilities
docker run --cap-drop=ALL --cap-add=NET_BIND_SERVICE ...

# Use security scanning
trivy image your-registry/ansible-updater:latest
```

### 2. Network Security
```bash
# Use dedicated network
docker network create ansible-secure

# Restrict port exposure
docker run -p 127.0.0.1:8080:8080 ...  # localhost only
```

### 3. Secret Management
```bash
# Use Docker secrets
docker secret create slack-webhook <file>

# Reference in compose
secrets:
  slack-webhook:
    external: true
```

## Monitoring and Logging

### Docker Logs
```bash
# View logs
docker-compose logs -f

# View specific service
docker-compose logs -f ansible-updater

# Tail last 100 lines
docker-compose logs --tail 100
```

### Health Checks
```bash
# Add to docker-compose.yml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Log Rotation
```bash
# Configure log rotation in docker-compose.yml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

## Troubleshooting

### Container won't start
```bash
docker-compose logs ansible-updater
docker-compose up --no-detach ansible-updater  # Run in foreground
```

### Out of disk space
```bash
docker system prune -a  # Remove unused images/containers
docker volume prune     # Remove unused volumes
```

### High memory usage
```bash
docker stats            # View resource usage
docker-compose down     # Restart containers
```

## Backup and Recovery

### Backup reports volume
```bash
docker run --rm \
  -v ansible-reports:/reports \
  -v $(pwd):/backup \
  ubuntu tar czf /backup/reports.tar.gz -C /reports .
```

### Restore reports volume
```bash
docker run --rm \
  -v ansible-reports:/reports \
  -v $(pwd):/backup \
  ubuntu tar xzf /backup/reports.tar.gz -C /reports
```

## Performance Tuning

```bash
# Increase resource limits
mem_limit: 1g
cpus: 0.5

# Use build cache
docker-compose build --no-cache  # Force rebuild

# Parallel execution
docker-compose up -d --scale=3   # Scale service
```

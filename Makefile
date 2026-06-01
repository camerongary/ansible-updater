.PHONY: help build up down logs test clean restart status

help:
	@echo "Ansible Update Manager - Available Commands"
	@echo ""
	@echo "Build & Run:"
	@echo "  make build       - Build Docker images"
	@echo "  make up          - Start all containers"
	@echo "  make down        - Stop all containers"
	@echo "  make restart     - Restart all containers"
	@echo ""
	@echo "Monitoring:"
	@echo "  make logs        - Tail container logs"
	@echo "  make status      - Show container status"
	@echo ""
	@echo "Testing:"
	@echo "  make test-ssh    - Test SSH connectivity"
	@echo "  make test-nmap   - Test network discovery"
	@echo "  make test-slack  - Test Slack notification"
	@echo "  make test-all    - Run all tests"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean       - Remove containers and reports"
	@echo "  make prune       - Remove unused Docker resources"
	@echo ""
	@echo "Development:"
	@echo "  make shell       - Shell into ansible container"
	@echo "  make playbook    - Run update playbook immediately"
	@echo ""

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "✓ Containers started"
	@echo "Dashboard: http://localhost"
	@echo "Logs: docker-compose logs -f"

down:
	docker-compose down

restart:
	docker-compose restart
	@echo "✓ Containers restarted"

status:
	docker-compose ps

logs:
	docker-compose logs -f

logs-ansible:
	docker-compose logs -f ansible-updater

logs-web:
	docker-compose logs -f ansible-web

test-ssh:
	@echo "Testing SSH connectivity..."
	docker-compose exec -it ansible-updater bash -c 'for host in $$(cat /tmp/live_hosts.txt); do echo "Testing $$host..."; ssh -o ConnectTimeout=5 root@$$host echo OK; done'

test-nmap:
	@echo "Running network discovery..."
	docker-compose exec ansible-updater bash -c 'nmap -sn 192.168.1.0/24 -oG - | grep "Up"'

test-slack:
	@echo "Testing Slack notification..."
	docker-compose exec ansible-updater python3 /scripts/slack_notifier.py

test-all: test-nmap test-ssh test-slack
	@echo "✓ All tests completed"

shell:
	docker-compose exec -it ansible-updater bash

playbook:
	@echo "Running update playbook immediately..."
	docker-compose exec ansible-updater ansible-playbook ansible/update-playbook.yml -i ansible/hosts.yml -v

reports:
	@echo "Recent reports:"
	@ls -lh reports/ | tail -10

clean:
	docker-compose down -v
	rm -f reports/*.json
	rm -f reports/index.html
	@echo "✓ Cleaned up containers and reports"

prune:
	docker system prune -f
	@echo "✓ Pruned unused Docker resources"

check-env:
	@if [ ! -f .env ]; then \
		echo "✗ .env file not found"; \
		echo "Run: cp .env.example .env"; \
		exit 1; \
	fi
	@echo "✓ .env file exists"
	@echo "Configuration:"
	@grep -v '^\#' .env | grep -v '^$$'

setup: check-env build up
	@echo "✓ Setup complete!"
	@echo "Dashboard: http://localhost"
	@echo "View logs: make logs"

version:
	@docker --version
	@docker-compose --version
	@echo ""
	@docker-compose exec ansible-updater ansible --version

.PHONY: help build up down logs logs-ansible logs-web test-ssh test-nmap test-slack test-all shell playbook reports clean prune check-env setup version status restart

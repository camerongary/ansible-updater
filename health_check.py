#!/usr/bin/env python3

import subprocess
import json
import sys
import os
from datetime import datetime
from pathlib import Path

class HealthChecker:
    def __init__(self):
        self.checks = []
        self.failures = []
        
    def run_check(self, name, command, description=""):
        """Run a health check command"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                timeout=10,
                text=True
            )
            
            status = "✓" if result.returncode == 0 else "✗"
            self.checks.append({
                "name": name,
                "status": "pass" if result.returncode == 0 else "fail",
                "description": description
            })
            
            if result.returncode != 0:
                self.failures.append({
                    "check": name,
                    "error": result.stderr or result.stdout,
                    "description": description
                })
            
            print(f"{status} {name}")
            if description:
                print(f"  {description}")
                
        except subprocess.TimeoutExpired:
            self.checks.append({
                "name": name,
                "status": "fail",
                "description": description
            })
            self.failures.append({
                "check": name,
                "error": "Command timeout",
                "description": description
            })
            print(f"✗ {name} (timeout)")
        except Exception as e:
            self.checks.append({
                "name": name,
                "status": "fail",
                "description": description
            })
            self.failures.append({
                "check": name,
                "error": str(e),
                "description": description
            })
            print(f"✗ {name} ({e})")

    def check_docker(self):
        """Check Docker installation and running"""
        print("\n🐳 Docker Checks")
        self.run_check(
            "Docker installed",
            "docker --version",
            "Verify Docker is installed"
        )
        self.run_check(
            "Docker daemon running",
            "docker ps > /dev/null 2>&1",
            "Verify Docker daemon is accessible"
        )
        self.run_check(
            "Docker Compose installed",
            "docker-compose --version",
            "Verify Docker Compose is installed"
        )

    def check_containers(self):
        """Check container status"""
        print("\n📦 Container Checks")
        self.run_check(
            "Containers running",
            "docker-compose ps | grep -q running",
            "Verify containers are running"
        )
        self.run_check(
            "Ansible updater container",
            "docker-compose ps | grep -q ansible-updater",
            "Verify ansible-updater container exists"
        )
        self.run_check(
            "Web server container",
            "docker-compose ps | grep -q ansible-web",
            "Verify ansible-web container exists"
        )

    def check_connectivity(self):
        """Check network connectivity"""
        print("\n🌐 Connectivity Checks")
        self.run_check(
            "DNS resolution",
            "docker-compose exec -T ansible-updater nslookup google.com > /dev/null 2>&1",
            "Verify DNS resolution works"
        )
        self.run_check(
            "Internet connectivity",
            "docker-compose exec -T ansible-updater ping -c 1 8.8.8.8 > /dev/null 2>&1",
            "Verify internet access"
        )

    def check_services(self):
        """Check running services"""
        print("\n⚙️ Service Checks")
        self.run_check(
            "Web dashboard (port 80)",
            "curl -s -o /dev/null -w '%{http_code}' http://localhost/ | grep -q 200",
            "Verify web dashboard is accessible"
        )
        self.run_check(
            "API health endpoint",
            "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health | grep -q 200",
            "Verify API health endpoint"
        )

    def check_files(self):
        """Check required files"""
        print("\n📁 File Checks")
        required_files = [
            ".env",
            "docker-compose.yml",
            "Dockerfile",
            "ansible/update-playbook.yml",
            "scripts/start.sh"
        ]
        
        for file in required_files:
            exists = os.path.exists(file)
            status = "✓" if exists else "✗"
            print(f"{status} {file}")
            self.checks.append({
                "name": f"File: {file}",
                "status": "pass" if exists else "fail",
                "description": ""
            })
            if not exists:
                self.failures.append({
                    "check": f"File: {file}",
                    "error": "File not found",
                    "description": ""
                })

    def check_ansible(self):
        """Check Ansible setup"""
        print("\n🔧 Ansible Checks")
        self.run_check(
            "Ansible installed",
            "docker-compose exec -T ansible-updater ansible --version > /dev/null 2>&1",
            "Verify Ansible is installed in container"
        )
        self.run_check(
            "Inventory file exists",
            "[ -f ansible/hosts.yml ] || docker-compose exec -T ansible-updater test -f /ansible/hosts.yml",
            "Verify Ansible inventory file"
        )

    def check_reports(self):
        """Check report generation"""
        print("\n📊 Report Checks")
        has_reports = len(list(Path("reports").glob("*.json"))) > 0 if Path("reports").exists() else False
        
        status = "✓" if has_reports or not Path("reports").exists() else "✗"
        print(f"{status} Reports directory")
        
        if Path("reports/index.html").exists():
            print("✓ Dashboard HTML generated")
        else:
            print("⚠ Dashboard HTML not yet generated (will be created on first run)")

    def check_config(self):
        """Check configuration"""
        print("\n⚙️ Configuration Checks")
        
        if os.path.exists(".env"):
            print("✓ .env file exists")
            with open(".env") as f:
                content = f.read()
                checks = {
                    "NETWORK_RANGE": "Network range configured" in content or "NETWORK_RANGE" in content,
                    "UPDATE_INTERVAL": "Update interval set" in content or "UPDATE_INTERVAL" in content,
                }
                for key, present in checks.items():
                    status = "✓" if present else "⚠"
                    print(f"  {status} {key}")
        else:
            print("✗ .env file missing")
            self.failures.append({
                "check": ".env file",
                "error": "File not found",
                "description": "Run: cp .env.example .env"
            })

    def print_summary(self):
        """Print health check summary"""
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["status"] == "pass")
        failed = total - passed
        
        print("\n" + "="*50)
        print("HEALTH CHECK SUMMARY")
        print("="*50)
        print(f"Total checks: {total}")
        print(f"Passed: {passed} ✓")
        print(f"Failed: {failed} ✗")
        
        if self.failures:
            print("\n⚠️ Issues Found:")
            for failure in self.failures:
                print(f"\n  {failure['check']}")
                if failure['error']:
                    print(f"    Error: {failure['error']}")
                if failure['description']:
                    print(f"    Help: {failure['description']}")
        
        if failed == 0:
            print("\n✓ All checks passed!")
            return 0
        else:
            print(f"\n✗ {failed} check(s) failed")
            return 1

    def export_json(self, filename="health_check.json"):
        """Export results to JSON"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "checks": self.checks,
            "summary": {
                "total": len(self.checks),
                "passed": sum(1 for c in self.checks if c["status"] == "pass"),
                "failed": sum(1 for c in self.checks if c["status"] == "fail")
            },
            "failures": self.failures
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n📄 Results exported to {filename}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Health check for Ansible Update System")
    parser.add_argument("--export", metavar="FILE", help="Export results to JSON file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    checker = HealthChecker()
    
    # Run all checks
    checker.check_docker()
    checker.check_containers()
    checker.check_files()
    checker.check_config()
    checker.check_ansible()
    checker.check_connectivity()
    checker.check_services()
    checker.check_reports()
    
    # Print summary
    exit_code = checker.print_summary()
    
    # Export if requested
    if args.export:
        checker.export_json(args.export)
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())

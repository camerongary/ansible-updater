FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive TZ=UTC

# Install dependencies
RUN apt-get update && apt-get install -y \
    nmap \
    python3-pip \
    openssh-client \
    sshpass \
    curl \
    jq \
    git \
    && rm -rf /var/lib/apt/lists/*

# ansible-core 2.14: dropped 'six' dependency (works with Debian 13 Python 3.12)
#   and predates PEP-563 annotations in module_utils (works with XCP-ng Python 3.6)
RUN pip3 install --no-cache-dir \
    "ansible-core>=2.14,<2.15" \
    flask \
    requests \
    jinja2

# Create working directories
RUN mkdir -p /ansible /reports /scripts /var/log/ansible

# Set working directory
WORKDIR /ansible

# Copy scripts
COPY scripts/ /scripts/
RUN chmod +x /scripts/*.sh /scripts/*.py

# Expose port for web interface
EXPOSE 8080

# Start the main orchestration script
CMD ["/scripts/start.sh"]

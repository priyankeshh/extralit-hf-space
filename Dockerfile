# Multi‐stage build to reduce image size
ARG EXTRALIT_VERSION=latest
ARG EXTRALIT_SERVER_IMAGE=extralit/argilla-server

# Base stage with common dependencies from Argilla server
FROM ${EXTRALIT_SERVER_IMAGE}:${EXTRALIT_VERSION} AS base
USER root

# Copy HF-Space startup scripts and Procfile
COPY scripts/start.sh /home/argilla/start.sh
COPY Procfile /home/argilla/Procfile
COPY requirements.txt /packages/requirements.txt
COPY app.py /home/argilla/app.py

# Install required APT dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      apt-transport-https \
      gnupg \
      wget \
      lsb-release && \
    # Elasticsearch signing key
    wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch \
      | gpg --dearmor -o /usr/share/keyrings/elasticsearch-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main" \
      | tee /etc/apt/sources.list.d/elastic-8.x.list && \
    # Redis signing key
    wget -qO - https://packages.redis.io/gpg \
      | gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" \
      | tee /etc/apt/sources.list.d/redis.list && \
    apt-get update

# Create data directory
RUN mkdir -p /data && chown argilla:argilla /data

# Install Elasticsearch (pinned) and fix permissions
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends elasticsearch=8.17.0 && \
    chown -R argilla:argilla /usr/share/elasticsearch /etc/elasticsearch /var/lib/elasticsearch /var/log/elasticsearch && \
    chown argilla:argilla /etc/default/elasticsearch

# Install Redis server
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends redis

# Install Python deps, utilities, then clean up
RUN pip install --no-cache-dir -r /packages/requirements.txt && \
    chmod +x /home/argilla/start.sh /home/argilla/Procfile && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends curl jq pwgen && \
    apt-get remove -y wget gnupg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /packages

# Copy Elasticsearch config
COPY config/elasticsearch.yml /etc/elasticsearch/elasticsearch.yml

USER argilla

# Environment variables for Elasticsearch
ENV ELASTIC_CONTAINER=true
ENV ES_JAVA_OPTS="-Xms1g -Xmx1g"

# Argilla home path for data
ENV ARGILLA_HOME_PATH=/data/argilla
ENV REINDEX_DATASETS=1

# Expose the HTTP port for FastAPI & Elastic
EXPOSE 80 9200 6379

# Start all services via Honcho/Procfile
CMD ["/bin/bash", "start.sh"]

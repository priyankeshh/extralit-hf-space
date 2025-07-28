#!/usr/bin/env bash
set -e

# HF-Spaces OAuth helpers (if using HF OAUTH)
export OAUTH2_HUGGINGFACE_CLIENT_ID=$OAUTH_CLIENT_ID
export OAUTH2_HUGGINGFACE_CLIENT_SECRET=$OAUTH_CLIENT_SECRET
export OAUTH2_HUGGINGFACE_SCOPE=$OAUTH_SCOPES

# Default credentials
DEFAULT_USERNAME=$(curl -s https://huggingface.co/api/users/${SPACE_CREATOR_USER_ID}/overview \
  | jq -r '.user' || echo "${SPACE_AUTHOR_NAME}")
export USERNAME="${USERNAME:-$DEFAULT_USERNAME}"
export PASSWORD="${PASSWORD:-$(pwgen -s 16 1)}"

# Start Elasticsearch, Redis, Argilla & extraction processes
honcho start

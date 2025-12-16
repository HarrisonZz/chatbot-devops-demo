#!/bin/bash
export PULUMI_CONFIG_PASSPHRASE=''
APP_NAME="ai-chatbot-app"
CLOUDFRONT_STATIC_URL="$(pulumi --cwd ../infra stack output assets_base_url)"
docker run -p 8501:8501 \
    -e CLOUDFRONT_STATIC_URL="${CLOUDFRONT_STATIC_URL}" \
    --env-file ../.env \
    "${APP_NAME}":latest
#!/bin/bash
set -e # 遇到錯誤自動停止

LOCAL_TEST=0
# --- 設定變數 ---
APP_DIR="../app"
APP_NAME="ai-chatbot-app"
TAG="latest"
VERSION="v0.3.1"
AWS_REGION="ap-northeast-1"
# 這裡先預留，等 Pulumi 跑完產生 ECR Repo 後，我們會透過環境變數傳進來

echo "🚀 Starting build process for ${APP_NAME}:${TAG}..."

# 1. 建置 Docker Image
# --platform linux/amd64 是為了確保在 Fargate 上能跑 (如果你是用 M1/M2 Mac 開發的話很重要)
echo "🔨 Building Docker Image..."
docker build --no-cache --platform linux/amd64 -t "${APP_NAME}:${TAG}" "${APP_DIR}"

echo "✅ Build success!"

if [[ "${LOCAL_TEST}" == 1 ]]; then
    exit 0
fi

ECR_REPO_URL="$(pulumi --cwd ../infra stack output ecr_repo_url --stack registry-dev)" 

if [[ "${ECR_REPO_URL}" != "sre-chatbot-local" ]]; then
    echo "☁️  Pushing to ECR: ${ECR_REPO_URL}..."
    
    # 登入 ECR
    aws ecr get-login-password --region "${AWS_REGION}" \
    | tr -d '\r' \
    | docker login --username AWS --password-stdin "${ECR_REPO_URL}"
    
    # Tagging
    docker tag "${APP_NAME}:${TAG}" "${ECR_REPO_URL}:${VERSION}"
    
    # Push
    docker push "${ECR_REPO_URL}:${VERSION}"
    
    echo "🎉 Pushed successfully!"
else
    echo "⚠️  ECR_REPO_URL not set. Skipping push. (Local build only)"
fi
#!/bin/bash
set -euo pipefail

FILE="../k8s/app/ai-chatbot/overlays/dev/kustomization.yaml"
IMG="533267110761.dkr.ecr.ap-northeast-1.amazonaws.com/ai-chatbot-app-dev"

# 1) tag = commit（優先用 CI 的 GITHUB_SHA，否則用本地 git）
COMMIT_SHA="${GITHUB_SHA:-$(git rev-parse HEAD)}"
TAG="${TAG:-$(echo "${COMMIT_SHA}" | cut -c1-7)}"

echo "Target file : ${FILE}"
echo "Target image: ${IMG}"
echo "New tag     : ${TAG}"
echo

# 安全檢查
[[ -f "$FILE" ]] || { echo "ERROR: file not found: $FILE" >&2; exit 1; }

# 2) 先備份
cp -a "$FILE" "${FILE}.bak"

# 3) 用 awk 只改目標 image block 的 newTag
awk -v img="$IMG" -v tag="$TAG" '
  $0 ~ "^[[:space:]]*-[[:space:]]*name:[[:space:]]*"img"[[:space:]]*$" { in_block=1; print; next }
  in_block && $0 ~ "^[[:space:]]*-[[:space:]]*name:" { in_block=0 }
  in_block && $0 ~ "^[[:space:]]*newTag:[[:space:]]*" {
    sub(/^[[:space:]]*newTag:[[:space:]]*.*/, "    newTag: " tag)
    in_block=0
  }
  { print }
' "$FILE" > "$FILE.tmp" && mv "$FILE.tmp" "$FILE"

# 4) 檢查是否真的改到了（避免 silent fail）
if diff -u "${FILE}.bak" "$FILE" >/dev/null; then
  echo "ERROR: No change detected. Possibly image name not matched or newTag not found." >&2
  echo "Restoring backup."
  mv "${FILE}.bak" "$FILE"
  exit 2
fi

echo "✅ Updated newTag successfully."
echo
echo "---- diff ----"
diff -u "${FILE}.bak" "$FILE" || true
echo "--------------"

echo
echo "Backup kept at: ${FILE}.bak"
echo "Tip: If ok, you can run: git diff && git add $FILE && git commit -m 'chore(gitops): bump dev image to ${TAG}'"

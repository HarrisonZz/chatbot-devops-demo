import pulumi
# 匯入我們寫好的模組 class
from modules.s3_website import StaticWebsite

# --- 使用模組 ---
# 你只要一行指令，就完成了 bucket, policy, sync 所有動作
chatbot_assets = StaticWebsite("ai-chatbot-demo", "../app/static")

# --- 輸出網址 ---
# 直接從物件屬性拿網址
pulumi.export("s3_website_url", chatbot_assets.website_url)
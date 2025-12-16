import pulumi
from src.components.edge import StaticAssetsCdn, CdnWaf
from src.components.registry.ecr_repo import EcrRepo

waf = CdnWaf(
    "ai-chatbot-cdn",
    rate_limit=30,
    evaluation_window_sec=300,
    # scope_down_path_prefix="/api",  # 需要時才開
)

assets = StaticAssetsCdn(
    "ai-chatbot-assets",
    folder_path="../app/static",
    web_acl_id=waf.web_acl_arn,
    tags={"app": "ai-chatbot", "env": pulumi.get_stack()},
)

repo = EcrRepo("ai-chatbot-app")

# S3 & CloudFront for static resources
pulumi.export("assets_base_url", assets.assets_base_url)
pulumi.export("distribution_id", assets.distribution_id)
pulumi.export("bucket_name", assets.bucket_name)

# ECR Repository
pulumi.export("ecr_repo_url", repo.repository_url)
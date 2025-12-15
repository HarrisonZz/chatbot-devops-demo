import pulumi
from src.components.edge import StaticAssetsCdn

assets = StaticAssetsCdn(
    "ai-chatbot-assets",
    folder_path="../app/static",
    tags={"app": "ai-chatbot", "env": pulumi.get_stack()},
)

pulumi.export("assets_base_url", assets.assets_base_url)
pulumi.export("distribution_id", assets.distribution_id)
pulumi.export("bucket_name", assets.bucket_name)
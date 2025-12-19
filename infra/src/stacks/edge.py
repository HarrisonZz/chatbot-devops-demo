import pulumi
from components.edge import StaticAssetsCdn, CdnWaf
from pathlib import Path
import pulumi_aws as aws

def deploy(env: str):

    protect = (env == "prod")

    waf = CdnWaf(
        f"ai-chatbot-cdn-{env}",
        rate_limit=30,
        evaluation_window_sec=300,
        opts=pulumi.ResourceOptions(protect=protect),
        # scope_down_path_prefix="/api",  # 需要時才開
    )

    assets = StaticAssetsCdn(
        f"ai-chatbot-assets-{env}",
        folder_path="../../app/static",
        web_acl_id=waf.web_acl_arn,
        tags={"app": "ai-chatbot", "env": env},
        opts=pulumi.ResourceOptions(protect=protect),
    )

    param = aws.ssm.Parameter(
        f"cloudfrontUrlParam-{env}",
        name=f"/ai-chatbot/{env}/cloudfront_url",
        type="String",         # 不是機密就 String；機密用 SecureString
        value=assets.assets_base_url,
        tags={"app": "ai-chatbot", "env": env},
            opts=pulumi.ResourceOptions(
            protect=protect,                   # 需要的話一起保護
            depends_on=[assets],               # 明確依賴（保守但穩）
        ),
    )

    pulumi.export("cloudfront_url_param", param.name)
    pulumi.export("cloudfront_url", param.value)
    pulumi.export("distribution_id", assets.distribution_id)
    pulumi.export("bucket_name", assets.bucket_name)
    pulumi.export("waf_web_acl_arn", waf.web_acl_arn)
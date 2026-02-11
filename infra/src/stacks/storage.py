import pulumi
import pulumi_aws as aws
from components.storage import ConversationTable


def deploy(env: str):
    """
    部署存儲層資源

    :param env: 環境 (dev, test, prod)
    """
    # 生產環境啟用保護
    protect = (env == "prod")

    # 創建對話表
    conv_table = ConversationTable(
        f"ai-chatbot-conversations-{env}",
        env=env,
        enable_ttl=(env != "prod"),  # 非生產環境啟用 TTL
        ttl_days=30,
        enable_pitr=(env == "prod"),  # 生產環境啟用時間點恢復
        opts=pulumi.ResourceOptions(protect=protect)
    )

    # 導出表名到 SSM Parameter Store (供應用使用)
    table_name_param = aws.ssm.Parameter(
        f"dynamodbTableParam-{env}",
        name=f"/ai-chatbot/{env}/dynamodb_table_name",
        type="String",
        value=conv_table.table_name,
        description=f"DynamoDB table name for chatbot conversations ({env})",
        tags={
            "app": "ai-chatbot",
            "env": env,
            "managed-by": "pulumi"
        },
        opts=pulumi.ResourceOptions(
            protect=protect,
            depends_on=[conv_table]
        )
    )

    # 導出 Outputs
    pulumi.export("table_name", conv_table.table_name)
    pulumi.export("table_arn", conv_table.table_arn)
    pulumi.export("table_id", conv_table.table_id)
    pulumi.export("table_name_param", table_name_param.name)
    pulumi.export("table_name_param_value", table_name_param.value)

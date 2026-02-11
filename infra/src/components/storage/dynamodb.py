import pulumi
import pulumi_aws as aws
from typing import Optional
from pulumi import ResourceOptions, Output


class ConversationTable(pulumi.ComponentResource):
    """
    DynamoDB table for storing chatbot conversations

    Table Schema:
    - Partition Key: session_id (String) - 會話唯一標識符
    - Sort Key: message_index (Number) - 消息序號 (0, 1, 2, ...)

    Attributes:
    - role: user | assistant
    - content: 消息內容
    - timestamp: ISO 8601 時間戳
    - created_at: 會話創建時間
    - session_title: 會話標題 (第一個用戶問題的前 50 字)
    - user_id: 用戶標識符 (暫時固定為 "default")

    GSI: user_id-created_at-index
    - Partition Key: user_id
    - Sort Key: created_at (降序)
    - 用於查詢用戶的會話列表
    """

    def __init__(
        self,
        name: str,
        env: str,
        enable_ttl: bool = False,
        ttl_days: int = 30,
        enable_pitr: bool = False,
        opts: Optional[ResourceOptions] = None
    ):
        """
        創建 DynamoDB 對話表

        :param name: 資源名稱
        :param env: 環境 (dev, test, prod)
        :param enable_ttl: 是否啟用 TTL 自動過期
        :param ttl_days: TTL 天數（僅當 enable_ttl=True 時有效）
        :param enable_pitr: 是否啟用時間點恢復（生產環境建議開啟）
        """
        super().__init__("pkg:storage:ConversationTable", name, None, opts)

        table_name = f"ai-chatbot-conversations-{env}"

        # 創建 DynamoDB 表
        self.table = aws.dynamodb.Table(
            f"{name}-table",
            name=table_name,
            billing_mode="PAY_PER_REQUEST",  # 按需付費，無需預置容量
            hash_key="session_id",
            range_key="message_index",

            # 定義屬性
            attributes=[
                aws.dynamodb.TableAttributeArgs(
                    name="session_id",
                    type="S"  # String
                ),
                aws.dynamodb.TableAttributeArgs(
                    name="message_index",
                    type="N"  # Number
                ),
                aws.dynamodb.TableAttributeArgs(
                    name="user_id",
                    type="S"  # String (用於 GSI)
                ),
                aws.dynamodb.TableAttributeArgs(
                    name="created_at",
                    type="S"  # String (ISO 8601 時間戳，用於 GSI 排序)
                ),
            ],

            # 全局二級索引 (GSI) - 用於查詢用戶的會話列表
            global_secondary_indexes=[
                aws.dynamodb.TableGlobalSecondaryIndexArgs(
                    name="user_id-created_at-index",
                    hash_key="user_id",
                    range_key="created_at",
                    projection_type="ALL",  # 投影所有屬性
                )
            ],

            # TTL 配置（可選）
            ttl=aws.dynamodb.TableTtlArgs(
                enabled=enable_ttl,
                attribute_name="ttl_timestamp"  # TTL 屬性名稱
            ) if enable_ttl else None,

            # 時間點恢復（生產環境建議啟用）
            point_in_time_recovery=aws.dynamodb.TablePointInTimeRecoveryArgs(
                enabled=enable_pitr
            ),

            # 服務器端加密（使用 AWS 托管密鑰）
            server_side_encryption=aws.dynamodb.TableServerSideEncryptionArgs(
                enabled=True
            ),

            tags={
                "app": "ai-chatbot",
                "env": env,
                "component": "storage",
                "managed-by": "pulumi"
            },

            opts=ResourceOptions(parent=self)
        )

        # 導出屬性
        self.table_name = self.table.name
        self.table_arn = self.table.arn
        self.table_id = self.table.id

        # 註冊輸出
        self.register_outputs({
            "table_name": self.table_name,
            "table_arn": self.table_arn,
            "table_id": self.table_id
        })

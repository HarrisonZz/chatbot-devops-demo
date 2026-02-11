import boto3
import uuid
from datetime import datetime
from typing import List, Dict, Optional
import pytz
from src.services.logging import get_logger

logger = get_logger()


class ConversationService:
    """對話持久化服務"""

    def __init__(self, table_name: str, region: str = "ap-northeast-1"):
        """
        初始化 DynamoDB 對話服務

        :param table_name: DynamoDB 表名
        :param region: AWS 區域
        """
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)
        self.tz = pytz.timezone("Asia/Taipei")
        logger.info(f"ConversationService initialized with table: {table_name}")

    def create_session(self) -> str:
        """
        創建新會話並返回 session_id

        :return: 新會話的 UUID
        """
        session_id = str(uuid.uuid4())
        logger.info(f"Created new session: {session_id}")
        return session_id

    def save_message(
        self,
        session_id: str,
        message_index: int,
        role: str,
        content: str,
        session_title: Optional[str] = None
    ):
        """
        保存單條消息到 DynamoDB

        :param session_id: 會話 ID
        :param message_index: 消息序號
        :param role: 角色 (user 或 assistant)
        :param content: 消息內容
        :param session_title: 會話標題（僅第一條消息需要）
        """
        timestamp = datetime.now(self.tz).isoformat()

        item = {
            'session_id': session_id,
            'message_index': message_index,
            'role': role,
            'content': content,
            'timestamp': timestamp,
            'user_id': 'default'  # 未來可擴展為真實用戶 ID
        }

        # 如果是第一條消息（助手的歡迎語），設置 created_at 和 session_title
        # 如果是第二條消息（第一條用戶消息），更新 session_title
        if message_index == 0:
            item['created_at'] = timestamp
            item['session_title'] = 'New Session'
        elif message_index == 1 and role == 'user':
            # 第一條用戶消息，設置為會話標題
            item['session_title'] = session_title or content[:50]

        try:
            self.table.put_item(Item=item)
            logger.info(
                f"Saved message to DynamoDB",
                extra={
                    "session_id": session_id,
                    "message_index": message_index,
                    "role": role
                }
            )
        except Exception as e:
            logger.error(
                f"Failed to save message to DynamoDB",
                extra={
                    "session_id": session_id,
                    "error": str(e)
                }
            )
            raise

    def load_session(self, session_id: str) -> List[Dict]:
        """
        加載會話的所有消息

        :param session_id: 會話 ID
        :return: 消息列表 [{"role": "user", "content": "..."}]
        """
        try:
            response = self.table.query(
                KeyConditionExpression='session_id = :sid',
                ExpressionAttributeValues={':sid': session_id},
                ScanIndexForward=True  # 按 message_index 升序
            )

            messages = [
                {"role": item["role"], "content": item["content"]}
                for item in response['Items']
            ]

            logger.info(
                f"Loaded session from DynamoDB",
                extra={"session_id": session_id, "message_count": len(messages)}
            )
            return messages

        except Exception as e:
            logger.error(
                f"Failed to load session from DynamoDB",
                extra={"session_id": session_id, "error": str(e)}
            )
            return []

    def list_sessions(self, limit: int = 10) -> List[Dict]:
        """
        列出最近的會話列表

        :param limit: 返回的會話數量限制
        :return: 會話列表 [{"session_id": "...", "session_title": "...", "created_at": "..."}]
        """
        try:
            response = self.table.query(
                IndexName='user_id-created_at-index',
                KeyConditionExpression='user_id = :uid',
                ExpressionAttributeValues={':uid': 'default'},
                ScanIndexForward=False,  # 降序（最新的在前）
                Limit=limit * 2  # 多查一些，因為需要過濾
            )

            # 只取每個會話的第一條用戶消息（message_index == 1）
            sessions = []
            seen_sessions = set()

            for item in response['Items']:
                session_id = item['session_id']
                # 避免重複，只取每個會話一次
                if session_id not in seen_sessions and item.get('message_index') == 1:
                    sessions.append({
                        "session_id": session_id,
                        "session_title": item.get("session_title", "Untitled"),
                        "created_at": item.get("created_at", item["timestamp"])
                    })
                    seen_sessions.add(session_id)

                if len(sessions) >= limit:
                    break

            logger.info(f"Listed {len(sessions)} sessions")
            return sessions

        except Exception as e:
            logger.error(f"Failed to list sessions: {str(e)}")
            return []

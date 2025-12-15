import streamlit as st
import boto3
import json
import time
import logging
import pytz
from datetime import datetime
from pythonjsonlogger import jsonlogger

BASE_SYSTEM_PROMPTS = [
    {
        "text": "You are a helpful and professional DevOps/SRE Assistant."
    },
    {
        "text": "You should answer questions concisely and use technical terminology where appropriate."
    }
]


# --- 1. 設定 Logging (O11y) ---
logger = logging.getLogger()
logHandler = logging.StreamHandler()
# 讓 Log 變成 JSON 格式，方便 CloudWatch 解析
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# --- 設定 AWS Bedrock ---
# 這裡假設你的 local 環境已經有 ~/.aws/credentials
# 或是你有 export AWS_ACCESS_KEY_ID / SECRET_KEY
client  = boto3.client(
    service_name='bedrock-runtime', 
    region_name='ap-northeast-1' # 記得改成你有開通模型的 Region
)

# 設定要使用的模型 ID (這裡用最便宜的 Claude 3 Haiku，或是改用 Titan)
MODEL_ID = "amazon.nova-lite-v1:0" 

def call_bedrock(prompt):

    start_time = time.time()

    tz = pytz.timezone('Asia/Taipei')
    current_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    
    # 建立動態的時間 Prompt
    time_prompt = {
        "text": f"The current time in Taipei is {current_time}."
    }
    combined_system_prompts = BASE_SYSTEM_PROMPTS + [time_prompt]

    messages = [
        {
            "role": "user",
            "content": [{"text": prompt}]
        }
    ]

    try:
        response = client.converse(
            modelId=MODEL_ID,
            messages=messages,
            system=combined_system_prompts,
            inferenceConfig={"maxTokens": 1000, "temperature": 0.7}
        )

        ranswer = response["output"]["message"]["content"][0]["text"]

        duration = time.time() - start_time

        logger.info("Bedrock invoked successfully", extra={
            "model_id": MODEL_ID,
            "latency": duration,
            "status": "success"
        })
        return ranswer

    except Exception as e:
        logger.error("Bedrock invocation failed", extra={
            "error": str(e),
            "model_id": MODEL_ID
        })
        return f"Error: {str(e)}"

# --- Streamlit UI 介面 ---
st.title("🤖 Simple AI Chatbot")
st.caption("SRE Assessment Demo: Generative AI Chatbot Lifecycle Management")
st.caption("🏗️ Architecture: AWS Bedrock + ECS Fargate | Infra: Pulumi & Ansible")

# 初始化對話歷史 (Session State)
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "Hello! I'm a AI Chat Robot. How can I help you?"}]

# 顯示過去的對話紀錄
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# 處理使用者輸入
if prompt := st.chat_input():
    # 1. 顯示使用者的訊息
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    # 2. 呼叫 AI 並顯示回應
    with st.chat_message("assistant"):
        response_text = call_bedrock(prompt)
        st.write(response_text)
    
    # 3. 儲存 AI 的回應到紀錄中
    st.session_state.messages.append({"role": "assistant", "content": response_text})
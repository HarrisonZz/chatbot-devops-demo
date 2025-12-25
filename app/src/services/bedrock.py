# src/services/bedrock.py
import time
import boto3
import pytz
from datetime import datetime
import streamlit as st

from src.prompts import build_system_prompts

@st.cache_resource
def get_bedrock_client(region_name: str):
    return boto3.client(service_name="bedrock-runtime", region_name=region_name)

def taipei_now_str() -> str:
    tz = pytz.timezone("Asia/Taipei")
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

def call_bedrock(
    prompt: str,
    *,
    client,
    model_id: str,
    max_tokens: int,
    temperature: float,
    logger,
) -> str:
    start_time = time.time()
    current_time = taipei_now_str()
    system_prompts = build_system_prompts(current_time)

    messages = [{"role": "user", "content": [{"text": prompt}]}]

    try:
        response = client.converse(
            modelId=model_id,
            messages=messages,
            system=system_prompts,
            inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
        )
        answer = response["output"]["message"]["content"][0]["text"]
        
        logger.info("Bedrock invoked successfully", extra={
            "model_id": model_id,
            "is_success": 1,
            "latency": time.time() - start_time,
            "status": "success",
        })
        return answer

    except Exception as e:
        logger.error("Bedrock invocation failed", extra={
            "error": str(e),
            "is_success": 0,
            "status": "error",
            "model_id": model_id,
        })
        return f"Error: {str(e)}"

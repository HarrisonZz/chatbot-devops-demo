# 使用輕量級的 Python 3.9 Slim 版本
FROM python:3.10-slim

# 設定工作目錄
WORKDIR /app

# 設定環境變數 (讓 Log 不會有 Buffer，直接印出來)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 1. 安裝系統依賴 (curl 用於 Healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 2. 複製 requirements.txt 並安裝 (利用 Docker Layer Caching)
COPY requirements.txt .
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

# 3. 複製應用程式代碼
COPY main.py .

# 4. 暴露 Streamlit 的預設 Port
EXPOSE 8501

# 5. 設定 Healthcheck (這對 ECS 很重要，壞掉會自動重啟)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# 6. 啟動指令
ENTRYPOINT ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
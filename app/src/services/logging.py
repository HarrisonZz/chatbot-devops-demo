import atexit
import logging
from pythonjsonlogger import jsonlogger

from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk.resources import Resource

OTLP_LOGS_ENDPOINT = "http://adot-collector-collector.observability.svc.cluster.local:4318/v1/logs"

def get_logger() -> logging.Logger:
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # 避免被 root logger 重複輸出

    # --- 1) Console handler: 只在沒有 StreamHandler 時加 ---
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        ch = logging.StreamHandler()
        ch.setFormatter(jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(message)s %(otelTraceID)s %(otelSpanID)s"
        ))
        logger.addHandler(ch)

    # --- 2) OTel handler: 只在沒有 LoggingHandler 時加 ---
    if not any(isinstance(h, LoggingHandler) for h in logger.handlers):
        try:
            # 建議帶 service.name，後端（CloudWatch/Grafana/等）可讀性差很多
            resource = Resource.create({"service.name": "ai-chatbot-app"})
            logger_provider = LoggerProvider(resource=resource)
            set_logger_provider(logger_provider)

            exporter = OTLPLogExporter(endpoint=OTLP_LOGS_ENDPOINT)
            # Streamlit/短生命週期：縮短 flush 週期比較直覺（可選）
            processor = BatchLogRecordProcessor(exporter, schedule_delay_millis=1000)
            logger_provider.add_log_record_processor(processor)

            otel_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
            logger.addHandler(otel_handler)

            # 確保退出時 flush/close（避免最後一批掉 log）
            atexit.register(logger_provider.shutdown)

        except Exception as e:
            # 這裡用 logger.exception 可能會遞迴（視 handler 而定），保守用 print
            print(f"Failed to setup OpenTelemetry logging: {e}")

    return logger

from datetime import datetime, timezone
import json
import logging
import sys
from app.core.context import get_request_id, get_tenant_id


class JSONFormatter(logging.Formatter):
    """Formats log records as structured, machine-parsable JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id() or None,
            "tenant_id": get_tenant_id() or None,
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


def setup_logging() -> None:
    """Configures root logger with JSON formatting on stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [handler]

    # Silence overly verbose third-party loggers
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn.error").handlers = [handler]
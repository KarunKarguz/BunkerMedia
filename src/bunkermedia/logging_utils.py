from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, self.datefmt or "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def setup_logging(logs_dir: Path, mode: str = "text") -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("bunkermedia")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    mode = mode.strip().lower()
    formatter: logging.Formatter
    if mode == "json":
        formatter = JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        logs_dir / "bunkermedia.log",
        maxBytes=2_000_000,
        backupCount=3,
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger

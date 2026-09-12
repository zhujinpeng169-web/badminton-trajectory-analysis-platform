"""服务事件日志。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .config import LOG_DIR, ensure_storage


def log_event(event: str, **fields: Any) -> None:
    """追加一条 JSONL 事件，避免记录模型提示词和敏感内容。"""
    ensure_storage()
    record = {"time": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    with (LOG_DIR / "service.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")

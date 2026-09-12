"""对 reasoning 证据进行可解释排序，限制发送给 Qwen 的上下文长度。"""

from __future__ import annotations

import re
from typing import Any


def _importance(item: dict[str, Any]) -> float:
    """根据事件类型、原始数值和证据文本计算 0-1 重要性。"""
    metric = str(item.get("metric", ""))
    text = f"{metric} {item.get('description', '')} {item.get('evidence', '')}"
    score = 0.35
    if "轨迹异常" in text or "anomaly" in text:
        score += 0.35
    if "方向突变" in text or "direction" in text:
        score += 0.25
    if "速度突增" in text or "speed" in text:
        score += 0.20
    if "高速" in text:
        score += 0.15
    value = item.get("value")
    try:
        numeric = abs(float(value))
        if "confidence" in str(item.get("unit", "")):
            score += min(0.15, numeric * 0.15)
        elif numeric > 100:
            score += 0.08
    except (TypeError, ValueError):
        pass
    # 重要性只用于排序，不表示击球类型、胜负或技术能力。
    return round(min(1.0, score), 3)


def rank_evidence(evidence: list[dict[str, Any]], limit: int = 20) -> dict[str, list[dict[str, Any]]]:
    """返回最多 limit 条证据，并保留原字段与新增 importance。"""
    ranked = []
    for item in evidence:
        output = {key: item.get(key) for key in ("metric", "value", "unit", "source", "description")}
        output["importance"] = _importance(item)
        ranked.append(output)
    ranked.sort(key=lambda item: (-item["importance"], str(item.get("source", "")), str(item.get("metric", ""))))
    return {"top_evidence": ranked[: max(0, limit)]}

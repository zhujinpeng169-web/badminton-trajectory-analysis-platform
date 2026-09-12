"""验证排序后的证据，避免范围混用和不受数据支持的推断。"""

from __future__ import annotations

from typing import Any


UNSUPPORTED_TERMS = ("击球次数", "杀球", "吊球", "技术动作", "胜负")


def _scope(metric: str) -> str:
    """从标准化 metric 名称识别证据粒度。"""
    if metric.startswith("rally["):
        return "rally"
    if metric.startswith("event["):
        return "event"
    if metric.startswith("player_") or ".player_" in metric:
        return "player"
    return "match"


def validate_evidence(evidence: list[dict[str, Any]], classification: dict[str, Any]) -> dict[str, Any]:
    """返回保留/移除证据和警告；不修改原始排序结果。"""
    intent = str(classification.get("intent", ""))
    rally_scope = bool(classification.get("rally_ids")) or "rally" in intent
    validated: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    warnings: list[str] = []
    for item in evidence:
        metric = str(item.get("metric", ""))
        text = f"{metric} {item.get('description', '')} {item.get('value', '')}"
        reason: list[str] = []
        reliability = 1.0
        if rally_scope and _scope(metric) == "match":
            removed.append({**item, "removal_reason": "回合问题禁止使用 match 级指标"})
            continue
        if any(term in text for term in UNSUPPORTED_TERMS):
            removed.append({**item, "removal_reason": "包含数据不支持的技术动作/击球/胜负推断"})
            continue
        if "speed_peak" in metric or "average_speed" in metric or "max_speed" in metric:
            try:
                value = float(item.get("value"))
            except (TypeError, ValueError):
                value = 0.0
            if value > 100:
                reliability = 0.25
                reason.append("速度超过 100 m/s 异常阈值，保留但降低可靠性")
                warnings.append(f"{metric}={value} 超过异常速度阈值")
            else:
                reason.append("速度未超过 100 m/s 异常阈值")
        else:
            reason.append("通过粒度和不支持推断检查")
        validated.append({"metric": item.get("metric"), "value": item.get("value"),
                          "unit": item.get("unit"), "source": item.get("source"),
                          "description": item.get("description"),
                          "reliability": reliability,
                          "validation_reason": "; ".join(reason)})
    return {"validated_evidence": validated, "removed_evidence": removed, "warnings": list(dict.fromkeys(warnings))}

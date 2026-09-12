"""Agent 自动评估指标计算。"""

from __future__ import annotations

from typing import Any


def intent_accuracy(rows: list[dict[str, Any]]) -> float:
    """计算 intent 完全匹配比例。"""
    return sum(r["intent_match"] for r in rows) / max(1, len(rows))


def tool_selection_accuracy(rows: list[dict[str, Any]]) -> float:
    """计算工具集合完全匹配比例。"""
    return sum(r["tool_match"] for r in rows) / max(1, len(rows))


def evidence_grounding_score(rows: list[dict[str, Any]]) -> float:
    """计算有证据且每条证据具备来源/单位的比例。"""
    scores = []
    for row in rows:
        evidence = row.get("evidence", [])
        if not evidence:
            scores.append(1.0 if row["expected_tools"] == [] else 0.0)
            continue
        valid = sum(bool(e.get("source") and e.get("unit") and "metric" in e) for e in evidence)
        scores.append(valid / len(evidence))
    return sum(scores) / max(1, len(scores))


def hallucination_rate(rows: list[dict[str, Any]]) -> float:
    """以 unsupported inference 标志和无证据工具回答作为代理幻觉率。"""
    bad = sum(bool(r.get("unsupported_terms")) or bool(r["expected_tools"] and not r.get("evidence")) for r in rows)
    return bad / max(1, len(rows))


def calculate_tool_efficiency(expected: list[str], actual: list[str]) -> float:
    """计算正确工具数量/实际调用工具数量；无需工具且实际为空时得分为 1。"""
    if not actual:
        return 1.0 if not expected else 0.0
    correct = sum(1 for tool in actual if tool in expected)
    return min(1.0, correct / len(actual))


def unsupported_inference_rate(rows: list[dict[str, Any]]) -> float:
    """统计 unsupported 问题未被正确拦截的比例。"""
    unsupported = [row for row in rows if row.get("expected_intent") == "unsupported_inference"]
    if not unsupported:
        return 0.0
    missed = sum(row.get("actual_intent") != "unsupported_inference" for row in unsupported)
    return missed / len(unsupported)


def memory_consistency_score(turn_groups: list[dict[str, Any]]) -> float:
    """统计多轮上下文中满足预期 subject/rally 继承的回合比例。"""
    checks = [check for group in turn_groups for check in group.get("checks", [])]
    if not checks:
        return 1.0
    return sum(bool(check.get("passed")) for check in checks) / len(checks)

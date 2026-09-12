"""问题驱动 Agent V1 的查询分类器。

本模块只负责解析问题和选择初始工具，不执行工具、不调用模型，也不修改旧 Planner。
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any


def unsupported_inference_detector(question: str) -> bool:
    """检测当前轨迹数据无法直接证明的胜负、动作、能力和战术推断。"""
    categories = {
        "outcome": ("赢", "输", "胜负", "获胜", "失败", "赢家", "比分", "结果"),
        "action": ("杀球", "扣杀", "吊球", "网前球", "高远球", "搓球", "挑球", "发球"),
        "ability": ("能力", "水平", "技术", "实力", "强弱", "优秀", "厉害"),
        "tactics": ("战术", "打法", "策略", "压制", "进攻", "防守能力"),
        # 这些表达是在请求主观评价，而不是查询轨迹中的可观测指标。
        "evaluation": ("适合比赛", "适合打球", "适合训练", "优势", "更强", "更好", "更厉害", "更有潜力"),
    }
    if any(keyword in question for keywords in categories.values() for keyword in keywords):
        return True
    # 评价型比较与普通的 A/B 数据比较不同；只有带疑问/评价语义时才拦截。
    comparison_patterns = (r"谁更", r"谁比较", r"哪个更", r"哪一个更")
    return any(re.search(pattern, question) for pattern in comparison_patterns)


def _subjects(question: str) -> list[str]:
    """识别运动员实体；A/B 仅表示 near/far 逻辑身份。"""
    found: list[str] = []
    if re.search(r"(?:运动员|球员)?\s*A(?![A-Za-z0-9])", question, re.IGNORECASE):
        found.append("player_A")
    if re.search(r"(?:运动员|球员)?\s*B(?![A-Za-z0-9])", question, re.IGNORECASE):
        found.append("player_B")
    if "近端" in question and "player_A" not in found:
        found.append("player_A")
    if "远端" in question and "player_B" not in found:
        found.append("player_B")
    return found


def _rallies(question: str) -> list[int]:
    """提取中文或英文回合编号；未指定回合时返回空数组。"""
    values: list[int] = []
    patterns = [r"第\s*(\d+)\s*回合", r"第\s*([一二三四五六七八九十]+)\s*回合", r"回合\s*(\d+)", r"rally\s*(\d+)"]
    for pattern in patterns:
        for match in re.finditer(pattern, question, re.IGNORECASE):
            token = match.group(1)
            if token.isdigit():
                value = int(token)
            else:
                numerals = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
                value = numerals.get(token, 0)
            if value <= 0:
                continue
            if value not in values:
                values.append(value)
    return values


def _has_explicit_scope(question: str, rally_ids: list[int]) -> bool:
    """识别回合、时间段或 frame 范围，供范围优先路由使用。"""
    if rally_ids or re.search(r"(?:前|后)?\s*\d+(?:\.\d+)?\s*(?:秒|s|sec|帧|frame|frames)", question, re.IGNORECASE):
        return True
    return bool(re.search(r"(?:frame|帧)\s*(?:范围|区间)?\s*\d+\s*(?:-|~|至|到)\s*\d+", question, re.IGNORECASE))


def classify(question: str) -> dict[str, Any]:
    """将用户问题转换为稳定的 Agent 路由 JSON。"""
    text = question.strip()
    if not text:
        raise ValueError("question 不能为空")
    subjects = _subjects(text)
    rally_ids = _rallies(text)
    lower = text.lower()
    constraints = {
        "must_use_json_fields_only": True,
        "must_cite_evidence": True,
        "allow_technical_inference": False,
        "allow_outcome_inference": False,
        "allow_training_advice": False,
    }

    # 不支持的推断必须优先于运动员/事件关键词分类。
    if unsupported_inference_detector(text):
        return {"question": text, "intent": "unsupported_inference", "subject": [],
                "rally_ids": [], "required_tools": [],
                "constraints": {"must_use_json_fields_only": True, "must_cite_evidence": False,
                                "allow_technical_inference": False, "allow_outcome_inference": False},
                "reason": "当前轨迹数据无法支持该推断", "confidence": 0.99}

    has_compare = ("比较" in text or "对比" in text or "谁的" in text) and len(subjects) >= 2
    has_event = any(word in text for word in ("关键事件", "事件", "高速", "突变", "异常", "击球"))
    has_rally = bool(rally_ids) or "回合" in text or "rally" in lower
    has_player = bool(subjects) or any(word in text for word in ("运动员", "球员", "移动", "距离", "覆盖", "站位"))

    # 指定数据范围优先于普通比较：范围内的 A/B 比较仍是回合级分析。
    # comparison 字段只在此类范围比较中显式标记，兼容旧 Planner 输入。
    scoped_range = _has_explicit_scope(text, rally_ids) and has_player
    scoped_comparison = scoped_range and has_compare
    if scoped_range:
        intent = "player_rally_analysis"
    elif has_event and has_rally:
        intent = "event_rally_analysis"
    elif has_compare:
        intent = "player_comparison"
    elif has_player and has_rally:
        intent = "player_rally_analysis"
    elif has_rally:
        intent = "rally_analysis"
    elif has_event:
        intent = "event_analysis"
    elif has_player:
        intent = "player_analysis"
    else:
        intent = "match_summary"

    tools: list[str] = []
    if intent in {"match_summary", "ball_trajectory_analysis", "data_quality"}:
        tools.append("get_match_summary")
    if intent in {"event_analysis", "event_rally_analysis"}:
        tools.append("get_event_analysis")
    if intent in {"rally_analysis", "player_rally_analysis", "event_rally_analysis"}:
        tools.append("get_rally_analysis")
    if intent in {"player_analysis", "player_comparison", "player_rally_analysis"}:
        tools.append("get_player_analysis")
    result = {"question": text, "intent": intent, "subject": subjects,
              "rally_ids": rally_ids, "required_tools": tools,
              "constraints": constraints, "confidence": 0.92}
    if scoped_comparison:
        result["comparison"] = True
    return result


def main() -> int:
    """命令行输出一个问题的分类 JSON。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="+", help="用户问题")
    args = parser.parse_args()
    print(json.dumps(classify(" ".join(args.question)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

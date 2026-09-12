"""根据用户问题选择最小必要分析工具。"""

from __future__ import annotations

import json
import sys
from typing import Any


def create_plan(classification: dict[str, Any]) -> dict[str, Any]:
    """根据 query_classifier 输出创建可执行的工具步骤。

    该接口不替换旧的关键词 plan；分类结果不完整时返回空步骤，交由调用方处理。
    """
    required_tools = classification.get("required_tools", [])
    if not isinstance(required_tools, list):
        raise ValueError("classification.required_tools 必须是列表")
    subjects = classification.get("subject", [])
    rally_ids = classification.get("rally_ids", [])
    if not isinstance(subjects, list) or not isinstance(rally_ids, list):
        raise ValueError("classification.subject 和 rally_ids 必须是列表")
    params_by_tool = {
        "get_match_summary": {},
        "get_event_analysis": {"rally_ids": rally_ids},
        "get_rally_analysis": {"rally_ids": rally_ids},
        "get_player_analysis": {"players": subjects},
    }
    supported = set(params_by_tool)
    steps = []
    for tool_name in required_tools:
        if tool_name not in supported:
            raise ValueError(f"不支持的工具: {tool_name}")
        steps.append({"tool": tool_name, "params": params_by_tool[tool_name]})
    return {"steps": steps}


def plan(question: str) -> dict[str, object]:
    """使用可解释关键词生成计划，不让模型自行决定数据范围。"""
    q = question.lower()
    tools = []
    if any(k in q for k in ("运动员", "球员", "player", "移动", "距离", "速度")):
        tools.append("get_player_analysis")
    if any(k in q for k in ("事件", "高速", "突变", "异常", "击球")):
        tools.append("get_event_analysis")
    if any(k in q for k in ("回合", "rally", "关键回合")):
        tools.append("get_rally_analysis")
    if not tools or any(k in q for k in ("比赛", "总体", "总结", "概览")):
        tools.insert(0, "get_match_summary")
    # 保持顺序稳定并消除重复工具。
    tools = list(dict.fromkeys(tools))
    return {"goal": question, "required_tools": tools}


def main() -> int:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        raise SystemExit("用法: python -m agent.planner '分析运动员A的问题'")
    print(json.dumps(plan(question), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

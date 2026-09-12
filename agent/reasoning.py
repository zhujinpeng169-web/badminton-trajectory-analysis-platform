"""将工具结果转换为可审计的证据结构，不生成技术动作或比赛结论。"""

from __future__ import annotations

from typing import Any


def _add(evidence: list[dict[str, Any]], metric: str, value: Any, unit: str,
         source: str, description: str) -> None:
    """追加一条带粒度说明的证据。"""
    if value is None:
        return
    evidence.append({"metric": metric, "value": value, "unit": unit,
                     "source": source, "description": description})


def _metric(evidence: list[dict[str, Any]], metric_name: str, item: Any,
            unit_or_source: str, source_or_description: str,
            description_or_granularity: str, granularity: str | None = None) -> None:
    """读取 name/value/unit 指标，并在描述中标明粒度。"""
    unit = unit_or_source if granularity is not None else None
    source = source_or_description if granularity is not None else unit_or_source
    description = description_or_granularity if granularity is not None else source_or_description
    level = granularity or description_or_granularity
    if isinstance(item, dict) and "value" in item:
        _add(evidence, metric_name, item.get("value"), item.get("unit", "unknown"),
             source, f"[{level}] {item.get('description', description)}")
    elif item is not None:
        _add(evidence, metric_name, item, unit or "unknown", source, f"[{level}] {description}")


def build_evidence(tool_results: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any]:
    """把工具输出整理为 Qwen 可引用的证据；不跨粒度推导新指标。"""
    question = classification.get("question", "")
    rally_ids = classification.get("rally_ids", []) or []
    subjects = classification.get("subject", []) or []
    intent = classification.get("intent", "")
    scope = {"intent": intent, "players": subjects, "rally_ids": rally_ids,
             "粒度规则": "仅使用与问题范围一致的 match/rally/event/player 原始字段"}
    evidence: list[dict[str, Any]] = []
    limitations = [
        "事件表示轨迹条件，不等同于已确认击球或具体技术动作。",
        "当前数据没有比分或人工真值，不能推断胜负或检测准确率。",
    ]

    if not rally_ids:
        summary = tool_results.get("get_match_summary", {})
        ball = summary.get("ball_analysis", {}) if isinstance(summary, dict) else {}
        for name, item in ball.items():
            if name == "shot_events":
                continue
            _metric(evidence, f"ball.{name}", item, "analysis.json.ball_analysis", "羽毛球统计指标", "match")
        players = summary.get("player_analysis", {}) if isinstance(summary, dict) else {}
        for player, metrics in players.items():
            if subjects and player not in subjects:
                continue
            for name, item in metrics.items():
                _metric(evidence, f"{player}.{name}", item, "analysis.json.player_analysis", "运动员统计指标", "player/match")
        direct_players = tool_results.get("get_player_analysis", {})
        for player, metrics in direct_players.items():
            if subjects and player not in subjects:
                continue
            for name, item in metrics.items():
                _metric(evidence, f"{player}.{name}", item, "analysis.json.player_analysis", "运动员统计指标", "player/match")

    rally_data = tool_results.get("get_rally_analysis", {})
    if isinstance(rally_data, dict):
        selected = rally_data.get("rallies", [])
        if rally_ids:
            selected = [r for r in selected if r.get("rally_id") in rally_ids]
        elif intent == "rally_analysis":
            selected = selected
        else:
            selected = []
        for rally in selected:
            rid = rally.get("rally_id")
            prefix = f"rally[{rid}]"
            _metric(evidence, f"{prefix}.duration", rally.get("duration"), "s", "rally_analysis.json", "回合持续时间", "rally")
            _metric(evidence, f"{prefix}.speed_peak", rally.get("speed_peak"), "rally_analysis.json", "回合速度峰值", "rally")
            _metric(evidence, f"{prefix}.ball_event_count", rally.get("ball_event_count"), "count", "rally_analysis.json", "回合内事件数量", "rally")
            _metric(evidence, f"{prefix}.direction_change_count", rally.get("direction_change_count"), "count", "rally_analysis.json", "回合内方向突变次数", "rally")
            distances = rally.get("player_distance", {})
            for player, item in distances.items():
                _metric(evidence, f"{prefix}.{player}.distance", item, "rally_analysis.json", "回合内运动员轨迹距离", "rally")

    events = tool_results.get("get_event_analysis", {})
    if isinstance(events, dict):
        selected_events = events.get("events", [])
        if rally_ids and isinstance(rally_data, dict):
            ranges = [(r.get("start_frame"), r.get("end_frame")) for r in rally_data.get("rallies", []) if r.get("rally_id") in rally_ids and r.get("start_frame") is not None and r.get("end_frame") is not None]
            selected_events = [e for e in selected_events if any(a <= e.get("frame", -1) <= b for a, b in ranges)]
        if intent in {"event_analysis", "event_rally_analysis"}:
            for event in selected_events:
                frame = event.get("frame")
                _add(evidence, f"event[{frame}].{event.get('event_type', 'unknown')}", event.get("confidence"), "confidence", "event_analysis.json", "[event] 轨迹事件置信度；不表示击球")
                _add(evidence, f"event[{frame}].time", event.get("time_sec"), "s", "event_analysis.json", "[event] 事件时间")
                _add(evidence, f"event[{frame}].evidence", event.get("evidence"), "text", "event_analysis.json", "[event] 原始字段证据")

    if rally_ids and intent == "player_rally_analysis":
        limitations.append("指定回合的运动员距离当前为 pixel；全局 player/match 指标未用于回合结论。")
    if not evidence:
        limitations.append("没有找到与该问题范围匹配的工具证据，数据不足，无法判断。")
    return {"question": question, "scope": scope, "evidence": evidence, "limitations": limitations}

"""从大量轨迹事件中筛选可供 Agent 阅读的关键事件。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def rank_events(data: dict, limit: int = 120) -> list[dict]:
    """按事件类型、置信度和时间间隔评分，并保留原始证据。"""
    weights = {"轨迹异常事件": 4.0, "方向突变事件": 3.0, "速度突增事件": 2.5, "高速事件": 2.0}
    ranked = []
    for event in data.get("events", []):
        event_type = event.get("event_type", "未知事件")
        confidence = float(event.get("confidence", 0.0))
        importance = weights.get(event_type, 1.0) * confidence
        ranked.append({"event_type": event_type, "time": event.get("time_sec"),
                       "frame": event.get("frame"), "importance": round(importance, 3),
                       "evidence": event.get("evidence", "")})
    ranked.sort(key=lambda e: (-e["importance"], e["frame"] if e["frame"] is not None else 0))
    selected = []
    for event in ranked:
        # 同类事件在 10 帧内视为同一簇，只保留评分最高者。
        if any(event["event_type"] == old["event_type"] and abs((event["frame"] or 0) - (old["frame"] or 0)) < 10 for old in selected):
            continue
        selected.append(event)
        if len(selected) >= limit:
            break
    selected.sort(key=lambda e: e["frame"] if e["frame"] is not None else 0)
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("event_analysis.json"))
    parser.add_argument("--output", type=Path, default=Path("important_events.json"))
    parser.add_argument("--limit", type=int, default=120)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    events = rank_events(data, args.limit)
    result = {"source": str(args.input), "input_event_count": len(data.get("events", [])),
              "important_event_count": len(events), "events": events,
              "limitations": ["重要性是规则排序分数，不代表击球类型或比赛结果。"]}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成: {args.output}，保留 {len(events)} / {len(data.get('events', []))} 个事件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

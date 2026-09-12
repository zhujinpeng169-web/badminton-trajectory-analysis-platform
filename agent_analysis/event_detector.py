"""从已有逐帧 CSV 检测可复核的轨迹事件，不判断具体技术动作。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _number(row: dict[str, str], field: str, default: float = -1.0) -> float:
    """读取数值字段，缺失或非法值统一返回默认值。"""
    try:
        return float(row.get(field, default))
    except (TypeError, ValueError):
        return default


def detect_events(trajectory_csv: Path, max_events: int = 1000) -> list[dict]:
    """依据速度、方向、异常标记生成事件列表。"""
    with trajectory_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        required = {"frame", "ball_speed_mps", "ball_direction_change_deg", "ball_jump_flag"}
        missing = sorted(required - fields)
        if missing:
            raise ValueError(f"事件检测需要字段 {missing}；实际字段为: {sorted(fields)}")
        rows = list(reader)
    events: list[dict] = []
    previous_speed = None
    last_by_type: dict[str, int] = {}
    for row in rows:
        frame = int(_number(row, "frame", 0))
        speed = _number(row, "ball_speed_mps")
        direction = _number(row, "ball_direction_change_deg")
        candidates = []
        # 超过 100 m/s 的值按既有导出规则视为异常跳变，不重复计入高速事件。
        if 50 <= speed <= 100:
            candidates.append(("高速事件", min(1.0, speed / 100.0), f"frame={frame}; ball_speed_mps={speed:.4f} >= 50"))
        if direction > 30:
            candidates.append(("方向突变事件", min(1.0, direction / 180.0), f"frame={frame}; ball_direction_change_deg={direction:.4f} > 30"))
        if previous_speed is not None and speed >= 0 and previous_speed >= 0 and speed > previous_speed * 1.5 and speed - previous_speed >= 5:
            candidates.append(("速度突增事件", min(1.0, (speed - previous_speed) / max(speed, 1.0)), f"frame={frame}; speed {previous_speed:.4f} -> {speed:.4f}"))
        if _number(row, "ball_jump_flag", 0) == 1:
            candidates.append(("轨迹异常事件", 1.0, f"frame={frame}; ball_jump_flag=1"))
        for event_type, confidence, evidence in candidates:
            if frame - last_by_type.get(event_type, -10**9) < 5:
                continue
            events.append({"frame": frame, "time_sec": round(_number(row, "time_sec"), 3),
                           "event_type": event_type, "confidence": round(confidence, 3), "evidence": evidence})
            last_by_type[event_type] = frame
            if len(events) >= max_events:
                return events
        if speed >= 0:
            previous_speed = speed
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-csv", type=Path, default=Path("output_coordinates/final/41_coordinates_locked.csv"))
    parser.add_argument("--output", type=Path, default=Path("event_analysis.json"))
    parser.add_argument("--max-events", type=int, default=10000)
    args = parser.parse_args()
    events = detect_events(args.trajectory_csv, args.max_events)
    result = {"source": str(args.trajectory_csv), "event_count": len(events), "events": events,
              "limitations": ["事件仅表示可观测轨迹条件，不等同于杀球、吊球或其他技术动作。"]}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成: {args.output}，事件数: {len(events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

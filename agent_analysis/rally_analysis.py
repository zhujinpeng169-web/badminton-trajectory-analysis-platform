"""把帧级轨迹和事件转换为可复核的回合级数据。"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from .event_detector import detect_events


def _num(row: dict[str, str], field: str, default: float = -1.0) -> float:
    """读取逐帧数值字段。"""
    try:
        return float(row.get(field, default))
    except (TypeError, ValueError):
        return default


def _player_distance(rows: list[dict[str, str]], prefix: str) -> float:
    """计算回合内像素坐标累计距离，明确单位为 pixel。"""
    points = [(_num(r, prefix + "_x"), _num(r, prefix + "_y")) for r in rows]
    points = [p for p in points if p[0] >= 0 and p[1] >= 0]
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))


def build_rally_analysis(trajectory_csv: Path, fps: float, max_missing_frames: int = 15) -> dict:
    """按球轨迹长缺失切分回合，并聚合事件和运动员像素移动距离。"""
    with trajectory_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = set(reader.fieldnames or [])
    required = {"frame", "ball_visible", "ball_speed_mps", "ball_direction_change_deg", "player_near_x", "player_near_y", "player_far_x", "player_far_y"}
    missing = sorted(required - fields)
    if missing:
        raise ValueError(f"回合分析需要字段 {missing}；实际字段为: {sorted(fields)}")
    visible_segments: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []
    last_visible = None
    for row in rows:
        frame = int(_num(row, "frame", 0))
        if _num(row, "ball_visible", 0) > 0 and _num(row, "ball_x") >= 0 and _num(row, "ball_y") >= 0:
            if current and frame - last_visible > max_missing_frames:
                visible_segments.append(current)
                current = []
            current.append(row)
            last_visible = frame
    if current:
        visible_segments.append(current)
    events = detect_events(trajectory_csv)
    rallies = []
    for rally_id, segment in enumerate(visible_segments, start=1):
        start = int(_num(segment[0], "frame", 0)); end = int(_num(segment[-1], "frame", start))
        rally_events = [e for e in events if start <= e["frame"] <= end]
        speeds = [_num(r, "ball_speed_mps") for r in segment
                  if _num(r, "ball_speed_mps") >= 0 and _num(r, "ball_jump_flag") != 1 and _num(r, "ball_speed_mps") <= 100]
        directions = sum(1 for r in segment if _num(r, "ball_direction_change_deg") > 30)
        rallies.append({
            "rally_id": rally_id,
            "start_frame": start,
            "end_frame": end,
            "duration": round((end - start) / fps, 3),
            "duration_unit": "s",
            "ball_event_count": len(rally_events),
            "speed_peak": {"value": round(max(speeds), 4) if speeds else None, "unit": "m/s", "description": "回合内有效二维投影速度峰值"},
            "direction_change_count": directions,
            "player_distance": {
                "player_A": {"value": round(_player_distance(segment, "player_near"), 3), "unit": "pixel", "description": "近端轨迹累计像素距离"},
                "player_B": {"value": round(_player_distance(segment, "player_far"), 3), "unit": "pixel", "description": "远端轨迹累计像素距离"},
            },
            "key_events": rally_events,
        })
    return {"source": {"trajectory_csv": str(trajectory_csv), "fps": fps, "max_missing_frames": max_missing_frames},
            "rally_count": len(rallies), "rallies": rallies,
            "limitations": ["回合由球轨迹连续性定义，不代表正式比分回合；运动员距离为像素单位，未换算为米。"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-csv", "--ball-csv", dest="trajectory_csv", type=Path, default=Path("output_coordinates/final/41_coordinates_locked.csv"))
    parser.add_argument("--fps", type=float, default=20.999984631446726)
    parser.add_argument("--max-missing-frames", type=int, default=15)
    parser.add_argument("--output", type=Path, default=Path("rally_analysis.json"))
    args = parser.parse_args()
    result = build_rally_analysis(args.trajectory_csv, args.fps, args.max_missing_frames)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成: {args.output}，回合数: {result['rally_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

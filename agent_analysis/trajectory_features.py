"""从已加载的轨迹对象计算可供大模型使用的特征。"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def metric(name: str, value: Any, unit: str, description: str) -> dict[str, Any]:
    """统一包装指标，明确名称、数值、单位和含义。"""
    return {"name": name, "value": value, "unit": unit, "description": description}


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def analyze_ball(rows: list[dict[str, Any]], fps: float, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """计算球轨迹特征；优先保留已有导出 JSON 中的米制统计。"""
    visible = [r for r in rows if r["visible"] and r["x"] >= 0 and r["y"] >= 0]
    speeds: list[float] = []
    directions = 0
    lengths = 0.0
    previous = None
    previous_angle = None
    possible_shots = []
    for current in visible:
        point = (current["x"], current["y"])
        if previous is not None:
            dt = max((current["frame"] - previous["frame"]) / fps, 1e-9)
            step = _distance(previous["point"], point)
            speed = step / dt
            speeds.append(speed)
            lengths += step
            angle = math.atan2(point[1] - previous["point"][1], point[0] - previous["point"][0])
            if previous_angle is not None and abs((angle - previous_angle + math.pi) % (2 * math.pi) - math.pi) > math.radians(30):
                directions += 1
            # 仅保留速度突增且画面纵向向下的候选点，并合并相邻候选，避免把一段连续高速误报成多个击球。
            baseline = sum(speeds[:-1]) / len(speeds[:-1]) if len(speeds) > 1 else 0.0
            descending = point[1] > previous["point"][1]
            far_enough = not possible_shots or current["frame"] - possible_shots[-1]["frame"] >= max(5, int(fps * 0.25))
            if baseline > 0 and speed > 1.5 * baseline and descending and far_enough and len(possible_shots) < 100:
                possible_shots.append({"frame": current["frame"], "time_sec": round(current["frame"] / fps, 3), "reason": "速度突增且轨迹向下，仅标记为可能击球"})
            previous_angle = angle
        previous = {"frame": current["frame"], "point": point}
    existing = existing or {}
    return {
        "total_frames": metric("total_frames", len(rows), "frames", "输入逐帧轨迹总帧数"),
        "valid_frames": metric("valid_frames", len(visible), "frames", "Visibility 有效且坐标非负的羽毛球帧数"),
        "average_speed_mps": metric("average_speed_mps", existing.get("ball_mean_speed_mps_filtered", sum(speeds) / len(speeds) if speeds else 0), "m/s", "羽毛球二维单应性投影平均速度"),
        "max_speed_mps": metric("max_speed_mps", existing.get("ball_max_speed_mps_filtered", max(speeds) if speeds else 0), "m/s", "羽毛球二维单应性投影最大速度"),
        "speed_change_count": metric("speed_change_count", sum(1 for a, b in zip(speeds, speeds[1:]) if b > a), "count", "相邻有效速度增加的次数"),
        "direction_changes": metric("direction_changes_gt30deg", existing.get("ball_direction_changes_gt30deg", directions), "count", "方向变化超过 30 度的次数"),
        "trajectory_length_m": metric("trajectory_length_m", existing.get("ball_distance_m_filtered", lengths), "m", "过滤异常跳变后的二维投影轨迹长度"),
        "anomaly_count": metric("anomaly_count", existing.get("ball_jump_frames", 0), "frames", "被已有导出标记为异常跳变的帧数"),
        "shot_events": possible_shots,
        "data_notes": ["速度和距离沿用已有二维单应性投影结果，不代表真实三维球速。"],
    }


def analyze_players(rows: list[dict[str, Any]], summary: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """计算近端/远端运动员特征，若有参考汇总则优先复用其米制指标。"""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["x"] >= 0 and row["y"] >= 0:
            grouped[row["player"]].append(row)
    output = {}
    for role in ("near", "far"):
        points = grouped.get(role, [])
        distances = sum(_distance((a["x"], a["y"]), (b["x"], b["y"])) for a, b in zip(points, points[1:]))
        speeds = [d * 30 for d in [_distance((a["x"], a["y"]), (b["x"], b["y"])) for a, b in zip(points, points[1:])]]
        ref = (summary or {}).get(f"{role}_player", {})
        output[f"player_{'A' if role == 'near' else 'B'}"] = {
            "distance_m": metric("distance_m", ref.get("total_distance_m", distances), "m", "运动员累计移动距离"),
            "average_speed_mps": metric("average_speed_mps", ref.get("mean_speed_mps", sum(speeds) / len(speeds) if speeds else 0), "m/s", "运动员平均速度"),
            "court_coverage_area_m2": metric("court_coverage_area_m2", ref.get("court_convex_hull_area_m2"), "m2", "有效球场坐标的凸包覆盖面积；缺失时为 null"),
            "left_ratio_pct": metric("left_ratio_pct", ref.get("left_pct"), "%", "位于左半场的有效帧比例"),
            "right_ratio_pct": metric("right_ratio_pct", ref.get("right_pct"), "%", "位于右半场的有效帧比例"),
            "front_ratio_pct": metric("front_ratio_pct", ref.get("front_pct"), "%", "位于前场的有效帧比例"),
            "mid_ratio_pct": metric("mid_ratio_pct", ref.get("mid_pct"), "%", "位于中场的有效帧比例"),
            "back_ratio_pct": metric("back_ratio_pct", ref.get("back_pct"), "%", "位于后场的有效帧比例"),
            "movement_style": metric("movement_style", "未推断", "label", "仅凭轨迹数据不推断技术风格"),
            "valid_frames": metric("valid_frames", len(points), "frames", "像素坐标非负的运动员帧数"),
        }
    return output

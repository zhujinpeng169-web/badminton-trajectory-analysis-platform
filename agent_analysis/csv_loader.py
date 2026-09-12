"""读取项目中的羽毛球和运动员轨迹 CSV。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _read_rows(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    """读取 CSV，并保留原始字段名以便发现字段不匹配。"""
    csv_path = Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"找不到 CSV 文件: {csv_path}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        return fields, list(reader)


def _number(value: str, field: str, row_number: int) -> float:
    """将字段转换为数字，错误时指出实际位置。"""
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 在第 {row_number} 行不是数字: {value!r}") from exc


def load_ball_csv(path: str | Path) -> list[dict[str, Any]]:
    """读取 TrackNet 格式的球轨迹，要求 Frame/Visibility/X/Y 字段。"""
    fields, rows = _read_rows(path)
    required = {"Frame", "Visibility", "X", "Y"}
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(
            f"羽毛球 CSV 缺少字段 {missing}；实际字段为: {fields}"
        )
    result = []
    for row_number, row in enumerate(rows, start=2):
        result.append({
            "frame": int(_number(row["Frame"], "Frame", row_number)),
            "visible": bool(int(_number(row["Visibility"], "Visibility", row_number))),
            "x": _number(row["X"], "X", row_number),
            "y": _number(row["Y"], "Y", row_number),
        })
    return result


def load_player_csv(path: str | Path) -> list[dict[str, Any]]:
    """读取独立 player CSV 或项目现有的近端/远端合并 CSV。"""
    fields, rows = _read_rows(path)
    combined = {"frame", "player_near_x", "player_near_y", "player_far_x", "player_far_y"}
    standalone = {"frame", "player", "x", "y"}
    if combined.issubset(fields):
        result = []
        for row_number, row in enumerate(rows, start=2):
            frame = int(_number(row["frame"], "frame", row_number))
            for role in ("near", "far"):
                x = _number(row[f"player_{role}_x"], f"player_{role}_x", row_number)
                y = _number(row[f"player_{role}_y"], f"player_{role}_y", row_number)
                result.append({"frame": frame, "player": role, "x": x, "y": y,
                               "source": row.get(f"player_{role}_source", "unknown")})
        return result
    if standalone.issubset(fields):
        return [{"frame": int(_number(row["frame"], "frame", n)),
                 "player": row["player"],
                 "x": _number(row["x"], "x", n),
                 "y": _number(row["y"], "y", n),
                 "source": row.get("source", "unknown")}
                for n, row in enumerate(rows, start=2)]
    raise ValueError(
        "运动员 CSV 字段不匹配；支持的字段集合为 "
        f"{sorted(combined)} 或 {sorted(standalone)}；实际字段为: {fields}"
    )

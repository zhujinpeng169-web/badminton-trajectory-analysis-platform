"""生成近端/远端运动员轨迹热力图，并报告 A/B 角色映射。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


def create_heatmap(trajectory_csv: Path, output: Path) -> dict:
    """使用现有 CSV 的近端(A)/远端(B)像素坐标生成双面板热力图。"""
    with trajectory_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        required = {"player_near_x", "player_near_y", "player_far_x", "player_far_y"}
        missing = sorted(required - fields)
        if missing:
            raise ValueError(f"热力图需要字段 {missing}；实际字段为: {sorted(fields)}")
        rows = list(reader)
    tracks = {}
    for label, prefix in (("player_A", "player_near"), ("player_B", "player_far")):
        points = []
        for row in rows:
            try:
                x, y = float(row[prefix + "_x"]), float(row[prefix + "_y"])
            except (TypeError, ValueError):
                continue
            if x >= 0 and y >= 0:
                points.append((x, y))
        tracks[label] = points
    fig, axes = plt.subplots(1, 2, figsize=(12, 6), constrained_layout=True)
    for ax, (label, points) in zip(axes, tracks.items()):
        if points:
            x, y = zip(*points)
            ax.hist2d(x, y, bins=(48, 32), cmap="magma", cmin=1)
            ax.plot(x, y, color="#40c4ff", alpha=0.18, linewidth=0.5)
        ax.set_title(f"{label}（near/far 映射）")
        ax.set_xlabel("像素 X")
        ax.set_ylabel("像素 Y")
        ax.set_xlim(0, 960)
        ax.set_ylim(544, 0)
        ax.grid(alpha=0.2)
    fig.suptitle("运动员轨迹热力图（A=player_near，B=player_far）")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160)
    plt.close(fig)
    return {
        "player_A": {"source_column": "player_near_x/y", "valid_points": len(tracks["player_A"])},
        "player_B": {"source_column": "player_far_x/y", "valid_points": len(tracks["player_B"])},
        "mapping_note": "A/B 是近端/远端逻辑身份，不是运动员真实姓名；位置划分沿用检测流程。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-csv", type=Path, default=Path("output_coordinates/final/41_coordinates_locked.csv"))
    parser.add_argument("--output", type=Path, default=Path("player_heatmap.png"))
    args = parser.parse_args()
    result = create_heatmap(args.trajectory_csv, args.output)
    print(f"已生成: {args.output}")
    print(f"player_A 有效点: {result['player_A']['valid_points']}；player_B 有效点: {result['player_B']['valid_points']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

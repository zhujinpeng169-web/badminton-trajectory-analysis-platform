"""将项目已有轨迹 CSV 和汇总结果转换为 Qwen 可读取的 analysis.json。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .csv_loader import load_ball_csv, load_player_csv
from .trajectory_features import analyze_ball, analyze_players
from .rally_analysis import build_rally_analysis
from .event_detector import detect_events


def _load_json(path: Path) -> dict:
    """读取可选的已有汇总 JSON。"""
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _load_player_summary(path: Path) -> dict[str, dict]:
    """读取已有运动员汇总表，保留文件中的实际数值。"""
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["player"]: {k: float(v) for k, v in row.items() if k != "player" and v != ""}
                for row in csv.DictReader(handle)}


def generate_analysis(ball_csv: Path, player_csv: Path, existing_json: Path, player_summary_csv: Path, video: str, fps: float) -> dict:
    """生成统一的、明确标注数据来源的分析对象。"""
    ball_rows = load_ball_csv(ball_csv)
    player_rows = load_player_csv(player_csv)
    existing = _load_json(existing_json)
    summary = _load_player_summary(player_summary_csv)
    return {
        "match_info": {"video": video, "fps": fps, "data_source": "已有检测结果"},
        "ball_analysis": analyze_ball(ball_rows, fps, existing),
        "player_analysis": analyze_players(player_rows, summary),
        "rally_analysis": build_rally_analysis(player_csv, fps),
        "event_analysis": {"events": detect_events(player_csv), "description": "可观测轨迹事件，不代表具体技术动作"},
        "key_events": [],
        "limitations": [
            "未提供人工真值，因此不输出检测准确率。",
            "击球事件仅在轨迹条件满足时标记为可能事件，不代表人工确认。",
        ],
    }


def build_qwen_input(analysis: dict) -> dict:
    """将分析对象包装为 Qwen 常用的 system/user 消息格式。"""
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一名专业羽毛球比赛数据分析专家。只能使用输入 JSON 中明确存在的字段和数值。"
                    "禁止根据轨迹推断未提供的击球类型、技术动作、胜负、习惯、意图或生理状态。"
                    "每个结论必须引用字段 name/value/unit；无法由数据证明时明确写‘数据不足，无法判断’。"
                    "不要把二维单应性投影速度当作真实三维球速，不要把可能事件当作已确认事件。"
                    "输出简洁 Markdown 报告，分为数据概览、可证实观察、数据限制；不输出无数据训练建议。"
                ),
            },
            {
                "role": "user",
                "content": "下面是比赛数据。请严格按系统规则分析，不要补充 JSON 之外的信息：\n"
                + json.dumps(analysis, ensure_ascii=False, indent=2),
            },
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ball-csv", type=Path, default=Path("output_tracknet/41_ball.csv"))
    parser.add_argument("--player-csv", type=Path, default=Path("output_coordinates/final/41_coordinates_locked.csv"))
    parser.add_argument("--existing-json", type=Path, default=Path("output_coordinates/final/41_coordinates_locked_ball_analysis.json"))
    parser.add_argument("--player-summary-csv", type=Path, default=Path("output_coordinates/reference/player_kinematics_table.csv"))
    parser.add_argument("--video", default="41.MP4")
    parser.add_argument("--fps", type=float, default=None)
    parser.add_argument("--output", type=Path, default=Path("analysis.json"))
    parser.add_argument("--qwen-output", type=Path, default=Path("qwen_input.json"))
    args = parser.parse_args()
    existing = _load_json(args.existing_json)
    fps = args.fps or float(existing.get("fps", 30.0))
    result = generate_analysis(args.ball_csv, args.player_csv, args.existing_json, args.player_summary_csv, args.video, fps)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    args.qwen_output.write_text(json.dumps(build_qwen_input(result), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成: {args.output}")
    print(f"已生成 Qwen 输入: {args.qwen_output}")
    print(f"羽毛球帧数: {result['ball_analysis']['total_frames']}")
    print(f"运动员分析对象: {', '.join(result['player_analysis'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

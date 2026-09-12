#!/usr/bin/env python3
"""Interactive local badminton trajectory analysis assistant.

The assistant keeps Qwen3-VL loaded once, combines project analysis files with
the conversation, and can attach sampled video frames for visual questions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import torch

from run_qwen3_vl import build_messages, load_model, sample_video


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "output_coordinates/final/41_coordinates_locked.csv"
DEFAULT_JSON = ROOT / "output_coordinates/final/41_coordinates_locked_ball_analysis.json"
DEFAULT_REPORT = ROOT / "output_coordinates/final/41_locked_tracking_report.md"
DEFAULT_FORMULAS = ROOT / "docs/数据分析公式说明.md"
DEFAULT_VIDEO = ROOT / "41.MP4"


def read_text(path: Path, limit: int = 7000) -> str:
    if not path.is_file():
        return f"[文件不存在] {path}"
    text = path.read_text(encoding="utf-8", errors="replace")
    return text if len(text) <= limit else text[:limit] + "\n[内容已截断]"


def build_data_context(csv_path: Path, json_path: Path, report_path: Path, formulas_path: Path) -> str:
    parts = [
        "项目名称：羽毛球轨迹分析系统。回答必须区分自动检测结果、二维投影结果和人工真值。",
        f"\n[羽毛球汇总 JSON]\n{read_text(json_path, 5000)}",
        f"\n[跟踪报告]\n{read_text(report_path, 7000)}",
        f"\n[公式说明]\n{read_text(formulas_path, 7000)}",
    ]
    if csv_path.is_file():
        df = pd.read_csv(csv_path)
        parts.append(
            "\n[逐帧 CSV 概况]\n"
            f"文件：{csv_path}\n行数：{len(df)}\n列：{', '.join(df.columns)}\n"
            f"前两行：\n{df.head(2).to_string(index=False)}\n"
            f"末两行：\n{df.tail(2).to_string(index=False)}"
        )
    return "\n".join(parts)


def frame_context(csv_path: Path, frame: int) -> str:
    if not csv_path.is_file():
        return f"未找到 CSV：{csv_path}"
    df = pd.read_csv(csv_path)
    if "frame" not in df.columns:
        return "CSV 没有 frame 列。"
    row = df.iloc[(df["frame"] - frame).abs().argsort()[:1]]
    return f"最接近请求帧 {frame} 的逐帧数据：\n{row.to_string(index=False)}"


def answer(model, processor, history: list[dict], context: str, question: str, video_media=None) -> str:
    content = []
    if video_media is not None:
        content.append({"type": "video", "video": video_media})
    content.append({
        "type": "text",
        "text": (
            "你的底层模型是 Qwen3-VL-8B-Instruct，当前以本地 4-bit 量化方式运行。"
            "当用户询问你的模型名称、身份或使用的模型时，直接回答：我是 Qwen3-VL-8B-Instruct，"
            "由本机 RTX 3090 本地部署。你的角色是羽毛球轨迹分析智能助手。"
            "优先使用提供的项目数据回答。"
            "不要把二维单应性投影速度说成真实三维球速；没有人工真值时，明确说明不能计算检测准确率。"
            "回答要给出依据，必要时引用帧号、时间、字段或公式。\n\n"
            f"项目资料：\n{context}\n\n用户问题：{question}"
        ),
    })
    messages = history + [{"role": "user", "content": content}]
    inputs = processor.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt"
    )
    inputs = {key: value.to(model.device) if hasattr(value, "to") else value for key, value in inputs.items()}
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=512)
    prompt_length = inputs["input_ids"].shape[1]
    text = processor.batch_decode(
        output[:, prompt_length:], skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0]
    history.extend([{"role": "user", "content": [{"type": "text", "text": question}]},
                    {"role": "assistant", "content": [{"type": "text", "text": text}]}])
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--analysis-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--formulas", type=Path, default=DEFAULT_FORMULAS)
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--model", default="Qwen/Qwen3-VL-8B-Instruct")
    parser.add_argument("--max-pixels", type=int, default=589824)
    args = parser.parse_args()

    model, processor = load_model(args.model, 4096, args.max_pixels)
    context = build_data_context(args.csv, args.analysis_json, args.report, args.formulas)
    history: list[dict] = []
    video_media = None
    print("羽毛球轨迹分析智能助手已启动。输入问题开始对话。")
    print("命令：:video 开始 结束 帧率 | :frame 帧号 | :clear | :quit")
    while True:
        try:
            raw = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue
        if raw in {":quit", ":exit", ":q"}:
            break
        if raw == ":clear":
            history.clear()
            video_media = None
            print("会话上下文已清除。")
            continue
        if raw.startswith(":frame "):
            try:
                frame = int(raw.split(maxsplit=1)[1])
                context += "\n\n" + frame_context(args.csv, frame)
                print(f"已加入第 {frame} 帧数据。")
            except ValueError:
                print("格式：:frame 1000")
            continue
        if raw.startswith(":video "):
            try:
                _, start, end, fps = raw.split()
                video_media, _ = sample_video(args.video, float(start), float(end), float(fps))
                print(f"已加载视频片段：{start}s-{end}s，采样 {len(video_media)} 帧。")
            except (ValueError, RuntimeError) as exc:
                print(f"视频命令失败：{exc}")
            continue
        try:
            print("助手> " + answer(model, processor, history, context, raw, video_media))
        except Exception as exc:
            print(f"推理失败：{exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

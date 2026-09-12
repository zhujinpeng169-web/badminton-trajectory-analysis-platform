#!/usr/bin/env python3
"""Run Qwen3-VL-8B-Instruct locally in 4-bit mode.

Examples:
  python tools/run_qwen3_vl.py --image frame.jpg --prompt "描述羽毛球和运动员位置"
  python tools/run_qwen3_vl.py --video 41.MP4 --start 10 --end 15 --fps 2 \
      --prompt "找出这段视频中的击球动作"
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import cv2
import numpy as np
import torch
from transformers import AutoProcessor, BitsAndBytesConfig, Qwen3VLForConditionalGeneration


MODEL_ID = "Qwen/Qwen3-VL-8B-Instruct"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path, help="Local image path")
    source.add_argument("--video", type=Path, help="Local video path")
    parser.add_argument("--prompt", required=True, help="Question or instruction for the model")
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--max-pixels", type=int, default=589824,
                        help="Maximum pixels per image/frame; lower this if VRAM is tight")
    parser.add_argument("--fps", type=float, default=2.0,
                        help="Video frames sampled per second")
    parser.add_argument("--start", type=float, default=0.0, help="Video start time in seconds")
    parser.add_argument("--end", type=float, default=None, help="Video end time in seconds")
    parser.add_argument("--min-pixels", type=int, default=4096)
    return parser


def load_model(model_id: str, min_pixels: int, max_pixels: int):
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. Run this with .venv/bin/python after fixing the NVIDIA runtime.")
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_id,
        quantization_config=quantization,
        torch_dtype=torch.float16,
        device_map="auto",
        low_cpu_mem_usage=True,
    )
    processor = AutoProcessor.from_pretrained(
        model_id,
        min_pixels=min_pixels,
        max_pixels=max_pixels,
    )
    return model, processor


def build_messages(args: argparse.Namespace) -> list[dict]:
    if args.image:
        if not args.image.is_file():
            raise FileNotFoundError(args.image)
        media = {"type": "image", "image": str(args.image.resolve())}
    else:
        if not args.video.is_file():
            raise FileNotFoundError(args.video)
        frames, _ = sample_video(args.video, args.start, args.end, args.fps)
        media = {
            "type": "video",
            "video": frames,
        }
    return [{"role": "user", "content": [media, {"type": "text", "text": args.prompt}]}]


def sample_video(path: Path, start: float, end: float | None, target_fps: float):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / source_fps if total_frames else 0.0
    start = max(0.0, float(start))
    end = duration if end is None else min(float(end), duration)
    if end <= start:
        cap.release()
        raise ValueError(f"Video interval is empty: start={start}, end={end}")
    step = max(1, int(round(source_fps / max(float(target_fps), 1e-3))))
    first = int(round(start * source_fps))
    last = min(total_frames, int(round(end * source_fps)))
    frames = []
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    frame_idx = first
    while frame_idx < last:
        ok, frame = cap.read()
        if not ok:
            break
        if (frame_idx - first) % step == 0:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        frame_idx += 1
    cap.release()
    if not frames:
        raise RuntimeError(f"No frames sampled from {path}")
    return np.asarray(frames), source_fps / step


def main() -> int:
    args = build_parser().parse_args()
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    model, processor = load_model(args.model, args.min_pixels, args.max_pixels)
    messages = build_messages(args)
    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    )
    inputs = {key: value.to(model.device) if hasattr(value, "to") else value
              for key, value in inputs.items()}
    with torch.inference_mode():
        generated = model.generate(**inputs, max_new_tokens=args.max_new_tokens)
    prompt_length = inputs["input_ids"].shape[1]
    answer = processor.batch_decode(
        generated[:, prompt_length:],
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    print(answer[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

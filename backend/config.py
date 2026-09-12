"""服务配置与存储路径。"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORAGE_ROOT = Path(os.getenv("BADMINTON_STORAGE_ROOT", str(ROOT / "backend" / "storage")))
UPLOAD_DIR = STORAGE_ROOT / "uploads"
TASK_DIR = STORAGE_ROOT / "tasks"
RESULT_DIR = STORAGE_ROOT / "results"
LOG_DIR = ROOT / "backend" / "logs"
TASK_WORKSPACE_ROOT = TASK_DIR
OLLAMA_MODEL = os.getenv("BADMINTON_QWEN_MODEL", "qwen3-vl:8b-instruct")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_TIMEOUT = int(os.getenv("BADMINTON_OLLAMA_TIMEOUT", "600"))
OLLAMA_MAX_TOKENS = int(os.getenv("BADMINTON_OLLAMA_MAX_TOKENS", "1024"))
MAX_WORKERS = int(os.getenv("BADMINTON_AGENT_WORKERS", "2"))
TRACKNET_BATCH_SIZE = int(os.getenv("BADMINTON_TRACKNET_BATCH_SIZE", "32"))
MAX_UPLOAD_MB = int(os.getenv("BADMINTON_MAX_UPLOAD_MB", "512"))
RENDER_VIDEO = os.getenv("BADMINTON_RENDER_VIDEO", "1").lower() not in {"0", "false", "no"}
DEVICE = os.getenv("BADMINTON_DEVICE", "auto")
TRACKNET_MODEL = Path(os.getenv("BADMINTON_TRACKNET_MODEL", str(ROOT / "external" / "TrackNetV3" / "ckpts" / "TrackNet_best.pt"))).expanduser()
INPAINT_MODEL = Path(os.getenv("BADMINTON_INPAINT_MODEL", str(ROOT / "external" / "TrackNetV3" / "ckpts" / "InpaintNet_best.pt"))).expanduser()
YOLO_MODEL = Path(os.getenv("BADMINTON_YOLO_MODEL", str(ROOT / "yolov8s-pose.pt"))).expanduser()
COURT_POINTS = os.getenv("BADMINTON_COURT_POINTS", "").strip()
BALL_SPEED_WARNING_MPS = float(os.getenv("BADMINTON_BALL_SPEED_WARNING_MPS", "100"))
PLAYER_SPEED_WARNING_MPS = float(os.getenv("BADMINTON_PLAYER_SPEED_WARNING_MPS", "15"))

def resolve_device(value: str | None = None) -> str:
    """Resolve one device for all pipeline stages; never hide invalid requests."""
    requested = (value if value is not None else DEVICE).strip().lower()
    if requested in {"", "auto"}:
        try:
            import torch
            if torch.cuda.is_available(): return "cuda"
            if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available(): return "mps"
        except ImportError:
            pass
        return "cpu"
    if requested.startswith("cuda"):
        try: available = __import__("torch").cuda.is_available()
        except ImportError: available = False
        if not available: raise RuntimeError("BADMINTON_DEVICE=cuda，但 CUDA 不可用；请设置 BADMINTON_DEVICE=cpu/mps")
        return requested
    if requested == "mps":
        try:
            torch = __import__("torch")
            available = bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
        except ImportError: available = False
        if not available: raise RuntimeError("BADMINTON_DEVICE=mps，但 MPS 不可用；请设置 BADMINTON_DEVICE=cpu")
        return requested
    if requested == "cpu": return requested
    raise RuntimeError(f"不支持的 BADMINTON_DEVICE: {requested}；可选 cpu、cuda、mps、auto")


def ensure_storage() -> None:
    """创建服务运行所需目录。"""
    for directory in (UPLOAD_DIR, TASK_DIR, RESULT_DIR, LOG_DIR):
        directory.mkdir(parents=True, exist_ok=True)

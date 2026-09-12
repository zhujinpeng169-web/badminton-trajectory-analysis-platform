"""单 Agent 可调用的数据读取工具。"""

from __future__ import annotations

import json
from contextvars import ContextVar
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_TASK_ROOT: ContextVar[Path | None] = ContextVar("agent_task_root", default=None)

def set_task_root(path: Path) -> None:
    _TASK_ROOT.set(path.resolve())

def reset_task_root() -> None:
    _TASK_ROOT.set(None)

def current_root() -> Path:
    return _TASK_ROOT.get() or ROOT


def _read(name: str) -> dict[str, Any]:
    """读取当前任务目录中的分析 JSON。"""
    path = current_root() / name
    if not path.is_file():
        raise FileNotFoundError(f"找不到分析文件: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_match_summary() -> dict[str, Any]:
    """返回比赛概览、球和运动员统计。"""
    data = _read("analysis.json")
    return {"match_info": data.get("match_info"), "ball_analysis": data.get("ball_analysis"),
            "player_analysis": data.get("player_analysis"), "limitations": data.get("limitations", [])}


def get_event_analysis() -> dict[str, Any]:
    """返回事件检测结果。"""
    # 若已生成排序结果，优先提供关键事件以控制上下文规模。
    ranked = current_root() / "important_events.json"
    return _read("important_events.json") if ranked.is_file() else _read("event_analysis.json")


def get_rally_analysis() -> dict[str, Any]:
    """返回回合级轨迹事件。"""
    return _read("rally_analysis.json")


def get_player_analysis() -> dict[str, Any]:
    """返回运动员字段和可用数据限制。"""
    return _read("analysis.json").get("player_analysis", {})

def get_quality_report() -> dict[str, Any]:
    """Return quality metadata for the current task only."""
    return _read("quality_report.json")

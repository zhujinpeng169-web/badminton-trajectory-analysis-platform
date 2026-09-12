"""轻量级分析会话记忆，只保存事实和用户上下文，不保存模型推断。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AnalysisMemory:
    """保存当前视频、最近问题、对象、路由和工具结果摘要。"""

    def __init__(self, path: Path | None = None, analysis_path: Path | None = None) -> None:
        self.path = path or Path("agent_memory.json")
        self.analysis_path = analysis_path or Path("analysis.json")
        self.data: dict[str, Any] = self._load()
        self._sync_video()

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._empty()
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else self._empty()
        except (OSError, json.JSONDecodeError):
            return self._empty()

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"video": None, "match_context": {}, "recent_question": None, "recent_subject": [],
                "recent_rally_ids": [], "recent_classification": None,
                "recent_plan": None, "tool_result_summaries": []}

    def _video_name(self) -> str | None:
        try:
            data = json.loads(self.analysis_path.read_text(encoding="utf-8"))
            return data.get("match_info", {}).get("video")
        except (OSError, json.JSONDecodeError):
            return None

    def _sync_video(self) -> None:
        """分析视频变化时自动清空旧上下文。"""
        current = self._video_name()
        if current and self.data.get("video") and current != self.data["video"]:
            self.data = self._empty()
        if current:
            self.data["video"] = current
            try:
                analysis = json.loads(self.analysis_path.read_text(encoding="utf-8"))
                self.data["match_context"] = analysis.get("match_info", {})
            except (OSError, json.JSONDecodeError):
                self.data["match_context"] = {"video": current}
        self.save()

    def enrich_classification(self, classification: dict[str, Any]) -> dict[str, Any]:
        """为省略主语的后续问题继承最近分析对象。"""
        result = dict(classification)
        if not result.get("subject") and self.data.get("recent_subject"):
            result["subject"] = list(self.data["recent_subject"])
        if result.get("rally_ids") and result.get("intent") == "rally_analysis" and result.get("subject"):
            result["intent"] = "player_rally_analysis"
            result["required_tools"] = ["get_rally_analysis", "get_player_analysis"]
        return result

    @staticmethod
    def summarize_tools(tool_results: dict[str, Any]) -> list[dict[str, Any]]:
        """只保存工具结果的结构摘要，不保存完整数据或模型文字。"""
        summaries = []
        for name, value in tool_results.items():
            summary: dict[str, Any] = {"tool": name, "type": type(value).__name__}
            if isinstance(value, dict):
                summary["keys"] = list(value.keys())
                for key in ("event_count", "rally_count", "important_event_count"):
                    if key in value:
                        summary[key] = value[key]
            summaries.append(summary)
        return summaries

    def update(self, question: str, classification: dict[str, Any], plan: dict[str, Any], tool_results: dict[str, Any]) -> None:
        """保存本轮事实和用户上下文；明确不保存 Qwen 输出。"""
        self.data.update({
            "recent_question": question,
            "recent_subject": classification.get("subject", []),
            "recent_rally_ids": classification.get("rally_ids", []),
            "recent_classification": classification,
            "recent_plan": plan,
            "tool_result_summaries": self.summarize_tools(tool_results),
        })
        self.save()

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

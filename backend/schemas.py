"""API 请求与响应模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    task_id: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=2000)


class TaskResponse(BaseModel):
    task_id: str
    status: Literal["uploaded", "processing", "ready", "answering", "completed", "failed", "cancelled"]
    message: str | None = None
    answer: str | None = None
    result_path: str | None = None
    stage: str | None = None
    pipeline_progress: int = 0
    artifacts: dict[str, str] = Field(default_factory=dict)
    quality_report_path: str | None = None


class TaskStatus(BaseModel):
    task_id: str
    status: Literal["uploaded", "processing", "ready", "answering", "completed", "failed", "cancelled"]
    progress: int = Field(ge=0, le=100)
    filename: str | None = None
    path: str | None = None
    question: str | None = None
    analysis_dir: str
    created_at: str
    updated_at: str
    result_path: str | None = None
    error: str | None = None
    routing: dict[str, Any] | None = None
    answer: str | None = None
    stage: str | None = None
    pipeline_progress: int = 0
    artifacts: dict[str, str] = Field(default_factory=dict)
    quality_report_path: str | None = None
    stages: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    interrupted: bool = False
    interruption_reason: str | None = None
    latest_result_path: str | None = None
    answer_history: list[str] = Field(default_factory=list)
    quality: str | None = None
    quality_warnings: list[str] = Field(default_factory=list)
    retry_count: int = 0
    previous_error: str | None = None
    retry_started_at: str | None = None


class UploadResponse(BaseModel):
    task_id: str
    filename: str
    path: str
    status: Literal["uploaded", "processing"] = "processing"
    stage: str | None = None
    pipeline_progress: int = 0
    artifacts: dict[str, str] = Field(default_factory=dict)

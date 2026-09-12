"""Agent 分析任务 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import AnalyzeRequest, TaskResponse
from ..task_manager import task_manager

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze", response_model=TaskResponse, status_code=202)
def analyze(request: AnalyzeRequest) -> TaskResponse:
    """提交问题驱动 Agent 分析任务。"""
    try:
        task = task_manager.submit_analysis(request.task_id, request.question)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return TaskResponse(task_id=task["task_id"], status=task["status"], message="问题已提交", stage=task.get("stage"), pipeline_progress=task.get("pipeline_progress", 0), artifacts=task.get("artifacts", {}), quality_report_path=task.get("quality_report_path"))

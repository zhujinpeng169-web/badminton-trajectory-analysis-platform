"""任务状态和结果 API。"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..schemas import TaskStatus
from ..task_manager import task_manager

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status/{task_id}", response_model=TaskStatus)
def status(task_id: str) -> TaskStatus:
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return TaskStatus(**task)


@router.get("/results/{task_id}")
def result(task_id: str) -> JSONResponse:
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["status"] not in {"ready", "completed"} or not task.get("result_path"):
        raise HTTPException(status_code=409, detail=f"任务尚未完成，当前状态: {task['status']}")
    try:
        with open(task["result_path"], encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"读取结果失败: {exc}") from exc
    return JSONResponse(content=data)

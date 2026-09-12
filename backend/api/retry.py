from fastapi import APIRouter, HTTPException
from ..task_manager import task_manager
from ..schemas import TaskResponse

router = APIRouter(prefix="/api", tags=["retry"])

@router.post("/retry/{task_id}", response_model=TaskResponse, status_code=202)
def retry(task_id: str) -> TaskResponse:
    try:
        task = task_manager.retry(task_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return TaskResponse(task_id=task["task_id"], status=task["status"], message="任务已重新排队", stage=task.get("stage"), pipeline_progress=task.get("pipeline_progress", 0), artifacts=task.get("artifacts", {}))

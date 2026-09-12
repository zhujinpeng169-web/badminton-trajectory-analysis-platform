from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from ..task_manager import task_manager

router = APIRouter(prefix="/api", tags=["artifacts"])
LOGICAL = {"ball_csv", "player_csv", "analysis_json", "quality_report", "event_analysis", "rally_analysis", "important_events", "analysis_video", "latest_result"}
def _safe_path(root, raw):
    path=Path(raw).expanduser().resolve()
    try: path.relative_to(Path(root).resolve())
    except ValueError: raise HTTPException(403,"产物路径不在当前任务目录")
    return path
@router.get("/artifacts/{task_id}/{artifact_name}")
def artifact(task_id, artifact_name):
    task=task_manager.get(task_id)
    if not task: raise HTTPException(404,"任务不存在")
    if artifact_name.startswith("answer_"):
        answer_id=artifact_name.removeprefix("answer_"); path=next((Path(p) for p in task.get("answer_history",[]) if Path(p).stem==f"agent_result_{answer_id}"),None)
    elif artifact_name in LOGICAL:
        path=Path(task.get("artifacts",{}).get(artifact_name,""));
        if artifact_name=="latest_result": path=Path(task.get("latest_result_path") or task.get("result_path") or "")
    else: raise HTTPException(403,"未登记的产物逻辑名称")
    if not path or not str(path): raise HTTPException(404,"产物不存在")
    path=_safe_path(task["workspace_dir"],str(path))
    if not path.is_file(): raise HTTPException(404,"产物不存在")
    return FileResponse(path,media_type={".json":"application/json",".csv":"text/csv",".md":"text/markdown",".mp4":"video/mp4"}.get(path.suffix.lower(),"application/octet-stream"))

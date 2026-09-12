"""文件上传 API。"""

from __future__ import annotations

import uuid
from pathlib import Path
try:
    import cv2
except ImportError:
    cv2 = None

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..config import UPLOAD_DIR, MAX_UPLOAD_MB, ensure_storage
from ..task_manager import task_manager
from ..schemas import UploadResponse

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    """保存上传文件；轨迹提取仍由现有流程负责。"""
    ensure_storage()
    original = Path(file.filename or "upload.bin").name
    source = Path(file.filename or "upload.bin")
    if source.suffix.lower() not in {".mp4", ".mov", ".avi", ".mkv"}:
        raise HTTPException(status_code=415, detail="仅支持 mp4、mov、avi、mkv 视频")
    if file.content_type and not file.content_type.startswith("video/") and file.content_type != "application/octet-stream":
        raise HTTPException(status_code=415, detail="MIME 类型与视频文件不匹配")
    target = UPLOAD_DIR / f"{uuid.uuid4().hex}{source.suffix.lower()}"
    # 同名上传不覆盖历史文件，任务 ID 由 TaskManager 生成。
    if target.exists():
        target = UPLOAD_DIR / f"{source.stem}_{uuid.uuid4().hex}{source.suffix}"
    try:
        total = 0
        with target.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(status_code=413, detail=f"文件超过 {MAX_UPLOAD_MB} MB 限制")
                handle.write(chunk)
        if cv2 is None:
            raise HTTPException(status_code=503, detail="服务缺少 OpenCV 依赖，请先安装 backend/requirements.txt")
        cap = cv2.VideoCapture(str(target))
        valid = cap.isOpened() and cap.get(cv2.CAP_PROP_FPS) > 0 and cap.get(cv2.CAP_PROP_FRAME_WIDTH) > 0 and cap.get(cv2.CAP_PROP_FRAME_HEIGHT) > 0 and cap.get(cv2.CAP_PROP_FRAME_COUNT) > 0
        cap.release()
        if not valid: raise HTTPException(status_code=422, detail="上传文件不是可读取的视频，或缺少有效 FPS/尺寸/帧数")
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    except OSError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"保存上传文件失败: {exc}") from exc
    task = task_manager.create_upload(original, str(target))
    return UploadResponse(task_id=task["task_id"], filename=original, path=str(target), stage=task.get("stage"), pipeline_progress=task.get("pipeline_progress",0), artifacts=task.get("artifacts",{}))

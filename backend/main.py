"""FastAPI 应用入口。

运行：``uvicorn backend.main:app --host 0.0.0.0 --port 8000``。
"""

from __future__ import annotations

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError as exc:  # 给未安装服务依赖的环境提供清晰错误。
    raise RuntimeError("服务依赖未安装，请执行: pip install -r backend/requirements.txt") from exc

from .api.analyze import router as analyze_router
from .api.status import router as status_router
from .api.upload import router as upload_router
from .api.artifacts import router as artifacts_router
from .api.retry import router as retry_router
from .config import ensure_storage

ensure_storage()
app = FastAPI(title="Badminton Trajectory Analysis Agent", version="0.9.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(upload_router)
app.include_router(analyze_router)
app.include_router(status_router)
app.include_router(artifacts_router)
app.include_router(retry_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "running"}

"""Persistent task lifecycle for video pipelines and agent answers."""
from __future__ import annotations
import json, threading, uuid, shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from .agent_runner import run_agent
from .config import MAX_WORKERS, RESULT_DIR, TASK_DIR, ensure_storage
from .video_pipeline import VideoPipeline

def _now(): return datetime.now(timezone.utc).isoformat()

class TaskManager:
    def __init__(self):
        ensure_storage(); self._lock=threading.RLock(); self._executor=ThreadPoolExecutor(max_workers=MAX_WORKERS,thread_name_prefix="badminton-task"); self._tasks={}; self._pipeline_running=set(); self._recover_processing()
    def _persist(self, task): (TASK_DIR/f"{task['task_id']}.json").write_text(json.dumps(task,ensure_ascii=False,indent=2),encoding="utf-8")
    def _load(self, task_id):
        p=TASK_DIR/f"{task_id}.json"
        try: return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
        except (OSError,json.JSONDecodeError): return None
    def _recover_processing(self):
        for p in TASK_DIR.glob("*.json"):
            task=self._load(p.stem)
            if not task: continue
            self._tasks[p.stem]=task
            if task.get("status") in {"processing","answering"}:
                task.update(status="failed", error="服务重启时任务中断，可重新上传或重试", interrupted=True, retryable=True, interruption_reason="process_restart", updated_at=_now()); self._persist(task)
    def _update(self, task_id, **changes):
        with self._lock:
            task=self._tasks[task_id]; task.update(changes,updated_at=_now()); self._persist(task); return dict(task)
    def create_upload(self, filename, path):
        task_id=uuid.uuid4().hex; workspace=TASK_DIR/task_id/"workspace"; analysis=workspace/"analysis"
        task={"task_id":task_id,"id":task_id,"filename":filename,"path":path,"status":"processing","progress":0,"pipeline_progress":0,"stage":"validate_video","stage_status":"queued","stages":{},"question":None,"workspace_dir":str(workspace),"analysis_dir":str(analysis),"created_at":_now(),"updated_at":_now(),"result_path":None,"quality_report_path":None,"quality":None,"quality_warnings":[],"artifacts":{},"error":None,"routing":None,"answer":None}
        with self._lock: self._tasks[task_id]=task; self._persist(task)
        if task_id not in self._pipeline_running:
            self._pipeline_running.add(task_id); self._executor.submit(self._run_pipeline,task_id)
        return dict(task)
    def get(self, task_id):
        with self._lock: task=self._tasks.get(task_id)
        if task is None: task=self._load(task_id); self._tasks[task_id]=task if task else None
        return dict(task) if task else None
    def submit_analysis(self, task_id, question):
        with self._lock:
            task=self.get(task_id)
            if task is None: raise KeyError(f"任务不存在: {task_id}")
            if not isinstance(question, str) or not question.strip():
                raise ValueError("问题不能为空")
            if task["status"] != "ready": raise ValueError(f"视频仍在分析或不可用，当前状态: {task['status']}；请等待 ready 后再提问")
            task.update(question=question,status="answering",progress=95,error=None,updated_at=_now(),answer_id=uuid.uuid4().hex); self._persist(task)
        # Pass the validated question into the worker.  Re-reading the mutable
        # task snapshot in the worker can race with lifecycle persistence and
        # yield the initial ``None`` question.
        self._executor.submit(self._run_agent,task_id,task["answer_id"],question); return dict(task)
    def _run_pipeline(self, task_id):
        task=self.get(task_id)
        pipeline = None
        try:
            pipeline = VideoPipeline(task,lambda **c:self._update(task_id,**c))
            pipeline.run(); current=self.get(task_id) or {}; artifacts=current.get("artifacts", {}); self._update(task_id,status="ready",progress=100,quality_report_path=artifacts.get("quality_report") or artifacts.get("quality_report_path"))
        except Exception as exc:
            if pipeline and pipeline.current_stage:
                pipeline.stage(pipeline.current_stage, "failed", int((self.get(task_id) or {}).get("pipeline_progress", 0)), error=str(exc), finished_at=_now())
            self._update(task_id,status="failed",progress=100,error=str(exc),stage_status="failed",retryable=True)
        finally:
            with self._lock: self._pipeline_running.discard(task_id)
    def _run_agent(self, task_id, answer_id, question):
        task=self.get(task_id)
        try:
            result=run_agent(question,task["analysis_dir"]); path=Path(task["analysis_dir"])/f"agent_result_{answer_id}.json"; path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); history=task.get("answer_history",[])+[str(path)]; self._update(task_id,status="ready",progress=100,result_path=str(path),latest_result_path=str(path),answer_history=history,routing=result.get("routing"),answer=result.get("report"),artifacts={**task.get("artifacts",{}),"latest_result":str(path)})
        except Exception as exc: self._update(task_id,status="failed",progress=100,error=str(exc),retryable=False)
    def retry(self, task_id):
        with self._lock:
            task=self.get(task_id)
            if not task: raise KeyError(f"任务不存在: {task_id}")
            if task.get("status") != "failed" or not task.get("retryable"): raise ValueError("仅允许 retryable 的 failed 任务重试")
            if task_id in self._pipeline_running: raise ValueError("任务已有流水线执行中")
            workspace=Path(task["workspace_dir"]); backup=workspace.with_name(workspace.name+".retry-backup"); before=dict(task)
            try:
                if backup.exists(): shutil.rmtree(backup)
                if workspace.exists(): workspace.rename(backup)
                workspace.mkdir(parents=True, exist_ok=True)
                task.update(status="processing",progress=0,pipeline_progress=0,error=None,previous_error=before.get("error"),retry_count=int(before.get("retry_count",0))+1,retry_started_at=_now(),retryable=False,interrupted=False,stages={},stage="validate_video",stage_status="queued",artifacts={},result_path=None,latest_result_path=None,quality=None,quality_warnings=[],answer=None,routing=None,answer_history=[],updated_at=_now()); self._persist(task)
                self._pipeline_running.add(task_id)
                self._executor.submit(self._run_pipeline,task_id)
            except Exception:
                shutil.rmtree(workspace,ignore_errors=True)
                if backup.exists(): backup.rename(workspace)
                self._tasks[task_id]=before; self._persist(before)
                self._pipeline_running.discard(task_id)
                raise
        if backup.exists(): shutil.rmtree(backup, ignore_errors=True)
        return dict(task)

task_manager=TaskManager()

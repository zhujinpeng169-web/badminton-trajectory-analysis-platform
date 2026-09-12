"""Task-local, resumable video analysis pipeline."""
from __future__ import annotations
import json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
try:
    import cv2
except ImportError:  # optional at import time so mock-pipeline tests can run
    cv2 = None

from .config import (COURT_POINTS, DEVICE, INPAINT_MODEL, RENDER_VIDEO, ROOT, TRACKNET_MODEL,
                     YOLO_MODEL, BALL_SPEED_WARNING_MPS, PLAYER_SPEED_WARNING_MPS, TRACKNET_BATCH_SIZE)
from .config import resolve_device
from agent_analysis.generate_analysis_json import generate_analysis
from agent_analysis.quality_report import build_quality_report, write_quality_report

def now() -> str: return datetime.now(timezone.utc).isoformat()

class PipelineError(RuntimeError): pass

class VideoPipeline:
    stages = ("validate_video", "detect_ball", "track_players", "export_coordinates", "generate_analysis", "render_video", "ready")
    def __init__(self, task: dict[str, Any], persist: Callable[..., None]):
        self.task=task; self.persist=persist
        self.workspace=Path(task["workspace_dir"]); self.analysis_dir=Path(task["analysis_dir"])
        self.workspace.mkdir(parents=True, exist_ok=True); self.analysis_dir.mkdir(parents=True, exist_ok=True)
        self.video=Path(task["path"])
        self.device = resolve_device(task.get("device") or DEVICE)
        self.artifacts: dict[str,str] = {}
        self.stage_times: dict[str,str] = {}
        self.stage_records: dict[str, dict[str, Any]] = {}
        self.current_stage: str | None = None
        for stage_name in self.stages:
            self.stage_records[stage_name] = {"stage": stage_name, "status": "queued", "progress": 0, "error": None, "started_at": None, "finished_at": None, "files": {}}

    def stage(self, name: str, status: str, progress: int, error: str|None=None, **extra: Any) -> None:
        record = self.stage_records.setdefault(name, {"stage": name})
        record.update({"status": status, "progress": progress, "error": error,
                       "started_at": self.stage_times.get(name) or extra.get("started_at"),
                       "finished_at": extra.get("finished_at"), "files": dict(self.artifacts)})
        self.persist(stage=name, stage_status=status, pipeline_progress=progress, stage_started_at=self.stage_times.get(name) or extra.get("started_at"),
                     stage_finished_at=extra.get("finished_at"), stage_error=error, artifacts=dict(self.artifacts), stages=dict(self.stage_records))

    def command(self, args: list[str], cwd: Path|None=None) -> subprocess.CompletedProcess[str]:
        result=subprocess.run(args, cwd=str(cwd or ROOT), text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise PipelineError(f"命令失败({result.returncode}): {' '.join(args)}\nstdout: {result.stdout[-2000:]}\nstderr: {result.stderr[-4000:]}")
        return result

    def run(self) -> None:
        self._validate(); self._detect_ball(); self._track_players(); self._export_coordinates(); self._generate_analysis()
        if RENDER_VIDEO: self._render()
        else: self.stage("render_video", "skipped", 97, finished_at=now(), error="BADMINTON_RENDER_VIDEO disabled")
        self.stage("ready", "completed", 100, finished_at=now())

    def _begin(self, name: str, progress: int) -> None:
        self.current_stage = name; self.stage_times[name] = now(); self.stage(name, "running", progress, started_at=self.stage_times[name])
    def _validate(self) -> None:
        self._begin("validate_video", 2)
        if cv2 is None: raise PipelineError("缺少 OpenCV 依赖，请执行 pip install -r backend/requirements.txt")
        if self.video.suffix.lower() not in {".mp4",".mov",".avi",".mkv"}: raise PipelineError("视频扩展名必须为 mp4、mov、avi 或 mkv")
        cap=cv2.VideoCapture(str(self.video));
        if not cap.isOpened(): raise PipelineError("OpenCV 无法打开视频")
        info={"fps":cap.get(cv2.CAP_PROP_FPS),"width":int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),"height":int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),"frame_count":int(cap.get(cv2.CAP_PROP_FRAME_COUNT))}; cap.release()
        if info["fps"]<=0 or info["width"]<=0 or info["height"]<=0 or info["frame_count"]<=0: raise PipelineError("视频缺少有效 FPS、宽度、高度或帧数")
        self.task["video_info"]=info; self.artifacts["video"] = str(self.video); self.stage("validate_video","completed",8,finished_at=now())
    def _require(self, path: Path, label: str) -> None:
        if not path.is_file(): raise PipelineError(f"缺少{label}文件: {path}。请将文件放到该路径，或通过对应 BADMINTON_* 环境变量覆盖。")
    def _detect_ball(self) -> None:
        self._begin("detect_ball", 10); self._require(TRACKNET_MODEL,"TrackNet 模型")
        outdir=self.workspace/"tracknet"; outdir.mkdir(exist_ok=True); args=[sys.executable,str(ROOT/"external/TrackNetV3/predict.py"),"--video_file",str(self.video),"--tracknet_file",str(TRACKNET_MODEL),"--save_dir",str(outdir),"--device",self.device,"--large_video","--batch_size",str(TRACKNET_BATCH_SIZE)]
        if INPAINT_MODEL.is_file(): args += ["--inpaintnet_file",str(INPAINT_MODEL)]
        self.command(args); stem=self.video.stem; ball=outdir/f"{stem}_ball.csv"; self._require(ball,"TrackNet 输出")
        self.artifacts["ball_csv"]=str(ball); self.stage("detect_ball","completed",32,finished_at=now())
    def _track_players(self) -> None:
        self._begin("track_players",34); self._require(YOLO_MODEL,"YOLO 模型"); self.persist(detector_started=now())
        if not COURT_POINTS: raise PipelineError("缺少 BADMINTON_COURT_POINTS；请配置四点 x1,y1,x2,y2,x3,y3,x4,y4，不能复用旧视频标定")
        self.artifacts["calibration"]="configured via BADMINTON_COURT_POINTS"; self.persist(detector_finished=now()); self.stage("track_players","completed",48,finished_at=now())
    def _export_coordinates(self) -> None:
        self._begin("export_coordinates",50); out=self.workspace/f"{self.video.stem}_coordinates.csv"
        args=[sys.executable,str(ROOT/"pipeline_code/export_frame_coordinates.py"),"--video",str(self.video),"--ball-csv",self.artifacts["ball_csv"],"--output",str(out),"--model",str(YOLO_MODEL),"--device",self.device,"--court-points",COURT_POINTS]
        self.command(args); self._require(out,"运动员坐标输出"); self.artifacts["player_csv"]=str(out); self.stage("export_coordinates","completed",65,finished_at=now())
    def _generate_analysis(self) -> None:
        self._begin("generate_analysis",67); analysis=generate_analysis(Path(self.artifacts["ball_csv"]),Path(self.artifacts["player_csv"]),Path(""),Path(""),str(self.video),float(self.task["video_info"]["fps"]))
        analysis["quality_report_path"]=str(self.analysis_dir/"quality_report.json"); analysis["degraded_inpaint"]=not INPAINT_MODEL.is_file()
        for name, value in (("analysis.json",analysis),("event_analysis.json",analysis.get("event_analysis",{})),("rally_analysis.json",analysis.get("rally_analysis",{})),("important_events.json",{"events":analysis.get("key_events",[])})):
            (self.analysis_dir/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
        quality=build_quality_report(self.task["video_info"],Path(self.artifacts["ball_csv"]),Path(self.artifacts["player_csv"]),bool(COURT_POINTS),BALL_SPEED_WARNING_MPS,PLAYER_SPEED_WARNING_MPS); write_quality_report(self.analysis_dir/"quality_report.json",quality); self.persist(quality=quality.get("overall_quality"), quality_warnings=quality.get("warnings", []))
        self.artifacts.update({"analysis_json":str(self.analysis_dir/"analysis.json"),"quality_report":str(self.analysis_dir/"quality_report.json"),"event_analysis":str(self.analysis_dir/"event_analysis.json"),"rally_analysis":str(self.analysis_dir/"rally_analysis.json"),"important_events":str(self.analysis_dir/"important_events.json")}); self.stage("generate_analysis","completed",84,finished_at=now())
    def _render(self) -> None:
        self._begin("render_video",86); out=self.workspace/f"{self.video.stem}_analysis.mp4"; args=[sys.executable,str(ROOT/"pipeline_code/overlay_player_analytics.py"),"--video_path",str(self.video),"--output_path",str(out),"--ball_csv",self.artifacts["ball_csv"],"--yolo_model",str(YOLO_MODEL),"--device",self.device,"--court_points",COURT_POINTS,"--no_select_court_points"]
        self.command(args); self._require(out,"分析视频"); self.artifacts["analysis_video"]=str(out); self.stage("render_video","completed",97,finished_at=now())

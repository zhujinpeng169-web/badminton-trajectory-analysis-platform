from pathlib import Path
import json
from backend.config import resolve_device
from agent import tools
from agent_analysis.quality_report import build_quality_report

def test_resolve_cpu():
    assert resolve_device("cpu") == "cpu"

def test_resolve_unavailable_cuda():
    try: resolve_device("cuda")
    except RuntimeError as exc: assert "CUDA" in str(exc)

def test_quality_empty_and_schema(tmp_path):
    ball=tmp_path/"ball.csv"; ball.write_text("Frame,Visibility,X,Y\n",encoding="utf-8")
    report=build_quality_report({"frame_count":0,"fps":30},ball,None,False)
    assert report["valid_frame_count"] == 0 and report["overall_quality"] == "poor"
    assert "schema_version" in report and "ball_speed_p95_mps" in report

def test_agent_quality_is_task_local(tmp_path):
    (tmp_path/"quality_report.json").write_text(json.dumps({"overall_quality":"poor"}),encoding="utf-8")
    token=tools._TASK_ROOT.set(tmp_path)
    try: assert tools.get_quality_report()["overall_quality"] == "poor"
    finally: tools._TASK_ROOT.reset(token)

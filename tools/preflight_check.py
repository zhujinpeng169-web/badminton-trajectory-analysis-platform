"""Machine-readable local environment preflight."""
from __future__ import annotations
import json, os, sys, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
def check():
    checks=[]
    def add(name,status,level,detail): checks.append({"name":name,"status":status,"level":level,"detail":detail})
    add("python", "ok", "required", sys.version.split()[0])
    for mod,level in (("cv2","required"),("ultralytics","required")):
        try: __import__(mod); add(mod,"ok",level,"importable")
        except Exception as exc: add(mod,"missing",level,str(exc))
    from backend.config import TRACKNET_MODEL, YOLO_MODEL, INPAINT_MODEL, COURT_POINTS, DEVICE
    for name,path,level in (("tracknet_model",TRACKNET_MODEL,"required"),("yolo_model",YOLO_MODEL,"required"),("inpaint_model",INPAINT_MODEL,"optional")):
        add(name,"ok" if path.is_file() else "missing",level,str(path))
    add("court_points","ok" if COURT_POINTS else "missing","required",COURT_POINTS or "BADMINTON_COURT_POINTS not set")
    add("device","ok","required",DEVICE)
    try:
        urllib.request.urlopen(os.getenv("OLLAMA_BASE_URL","http://127.0.0.1:11434")+"/api/tags",timeout=2); add("ollama","ok","required","reachable")
    except Exception as exc: add("ollama","unavailable","required",str(exc))
    for cmd in ("node","npm"):
        import shutil; value=shutil.which(cmd); add(cmd,"ok" if value else "missing","warning",value or "not found")
    return {"schema_version":"1.0","checks":checks,"ok":all(x["status"]=="ok" or x["level"]!="required" for x in checks)}
if __name__=="__main__": print(json.dumps(check(),ensure_ascii=False,indent=2))

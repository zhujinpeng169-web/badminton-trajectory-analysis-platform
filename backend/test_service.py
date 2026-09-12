"""HTTP smoke test for a running local service.

Usage: python backend/test_service.py --base-url http://127.0.0.1:8000 --video 41.MP4
"""
from __future__ import annotations
import argparse, sys, time
from pathlib import Path
import requests

def wait_status(session, base, task_id, wanted, timeout):
    deadline=time.monotonic()+timeout; last=None
    while time.monotonic()<deadline:
        data=session.get(f"{base}/api/status/{task_id}",timeout=30).json()
        if data.get("status") != last:
            print(f"status={data.get('status')} stage={data.get('stage')} progress={data.get('pipeline_progress')}" ); last=data.get("status")
        if data.get("status") in wanted: return data
        time.sleep(2)
    raise TimeoutError(f"timeout waiting for {wanted}")

def run(base_url: str, video: Path, questions: list[str], timeout: int) -> int:
    base=base_url.rstrip("/"); session=requests.Session()
    with video.open("rb") as stream:
        response=session.post(f"{base}/api/upload",files={"file":(video.name,stream,"video/mp4")},timeout=120)
    response.raise_for_status(); task_id=response.json()["task_id"]; print(f"upload task_id={task_id}")
    status=wait_status(session,base,task_id,{"ready","failed"},timeout)
    if status["status"] == "failed":
        print(f"failed stage={status.get('stage')} error={status.get('error','')[-1000:]}",file=sys.stderr); return 1
    for question in questions:
        response=session.post(f"{base}/api/analyze",json={"task_id":task_id,"question":question},timeout=30); response.raise_for_status()
        status=wait_status(session,base,task_id,{"ready","completed","failed"},timeout)
        if status["status"] == "failed":
            print(f"failed stage={status.get('stage')} error={status.get('error','')[-1000:]}",file=sys.stderr); return 1
        result=session.get(f"{base}/api/results/{task_id}",timeout=30); result.raise_for_status(); answer=result.json().get("report","")
        print(f"answer chars={len(answer)}")
        if "获胜" in question or "谁赢" in question:
            assert "数据不足" in answer or "无法判断" in answer
    return 0

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--base-url",default="http://127.0.0.1:8000"); parser.add_argument("--video",type=Path,default=Path("41.MP4")); parser.add_argument("--question",action="append",dest="questions"); parser.add_argument("--timeout",type=int,default=900); args=parser.parse_args()
    if not args.video.is_file(): raise SystemExit(f"找不到视频: {args.video}")
    return run(args.base_url,args.video,args.questions or ["分析运动员A","能否判断谁获胜"],args.timeout)
if __name__ == "__main__": raise SystemExit(main())

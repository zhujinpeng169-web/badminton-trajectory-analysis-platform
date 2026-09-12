"""Interactively select TL, TR, BR, BL court corners from a video frame."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import cv2

def select(video: Path, frame_index: int, output: Path) -> dict:
    cap=cv2.VideoCapture(str(video))
    if not cap.isOpened(): raise RuntimeError(f"Cannot open video: {video}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index); ok, frame=cap.read(); cap.release()
    if not ok: raise RuntimeError(f"Cannot read frame {frame_index}")
    points=[]; canvas=frame.copy()
    def callback(event,x,y,flags,param):
        del flags,param
        if event == cv2.EVENT_LBUTTONDOWN and len(points)<4:
            points.append([int(x),int(y)]); cv2.circle(canvas,(x,y),6,(0,0,255),-1); cv2.putText(canvas,str(len(points)),(x+8,y-8),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,255,255),2)
    window="Select TL -> TR -> BR -> BL; press Enter to save, Esc to cancel"
    cv2.namedWindow(window,cv2.WINDOW_NORMAL); cv2.setMouseCallback(window,callback)
    while True:
        cv2.imshow(window,canvas); key=cv2.waitKey(20)&0xFF
        if key==27: raise RuntimeError("Selection cancelled")
        if key in (10,13):
            if len(points)!=4: raise RuntimeError("Select exactly four points in TL, TR, BR, BL order")
            break
    cv2.destroyAllWindows(); result={"video":video.name,"frame":frame_index,"points":points}; output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); print("BADMINTON_COURT_POINTS="+','.join(str(v) for p in points for v in p)); return result

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("video",type=Path); parser.add_argument("--frame",type=int,default=0); parser.add_argument("--output",type=Path,default=Path("court_points.json")); args=parser.parse_args(); select(args.video,args.frame,args.output)

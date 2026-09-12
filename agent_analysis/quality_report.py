"""Stable, defensive quality metrics for task-local trajectory exports."""
from __future__ import annotations
import csv, json, math
from pathlib import Path
from typing import Any
SCHEMA_VERSION = "1.0"
BALL_REQUIRED = ({"Frame", "frame"}, {"Visibility", "ball_visible"}, {"X", "ball_x"}, {"Y", "ball_y"})
PLAYER_SCHEMAS = (
    {"frame", "player_near_x", "player_near_y", "player_far_x", "player_far_y"},
    {"frame", "player", "x", "y"},
)

def _missing_fields(fieldnames, required_sets):
    fields = set(fieldnames or [])
    return sum(1 for alternatives in required_sets if not any(name in fields for name in alternatives))

def _player_missing_fields(fieldnames):
    fields = set(fieldnames or [])
    if not fields:
        return len(PLAYER_SCHEMAS[0])
    if any(schema.issubset(fields) for schema in PLAYER_SCHEMAS):
        return 0
    return min(len(schema - fields) for schema in PLAYER_SCHEMAS)

def _rows(path, required_sets=(), player_schema=False):
    if not path or not path.is_file(): return [], 0, len(required_sets)
    parse_errors=0
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader=csv.DictReader(f); rows=[]
            missing_fields = _player_missing_fields(reader.fieldnames) if player_schema else _missing_fields(reader.fieldnames, required_sets)
            for raw in reader:
                if None in raw: parse_errors += 1
                rows.append(raw)
            return rows, parse_errors, missing_fields
    except (OSError, UnicodeError, csv.Error): return [], 1, len(required_sets)
def _num(row, *names, default=float("nan")):
    for name in names:
        try:
            value=float(row.get(name, ""))
            if math.isfinite(value): return value
        except (TypeError, ValueError): pass
    return default
def _percentile(values, p):
    if not values: return None
    values=sorted(values); index=(len(values)-1)*p; low=math.floor(index); high=math.ceil(index)
    return round(values[low]+(values[high]-values[low])*(index-low),4)
def build_quality_report(video_info, ball_csv, player_csv, calibration_available, ball_speed_warning=100.0, player_speed_warning=15.0):
    balls,b_parse,b_missing=_rows(ball_csv, BALL_REQUIRED); players,p_parse,p_missing=_rows(player_csv, player_schema=True); frame_count=max(0,int(video_info.get("frame_count",0) or 0)); fps=float(video_info.get("fps",0) or 0)
    frame_numbers=[_num(r,"Frame","frame") for r in balls]
    valid=[]
    for row, frame in zip(balls, frame_numbers):
        visibility=_num(row,"Visibility","ball_visible")
        x=_num(row,"X","ball_x")
        y=_num(row,"Y","ball_y")
        valid.append(math.isfinite(frame) and math.isfinite(visibility) and visibility > 0 and math.isfinite(x) and x >= 0 and math.isfinite(y) and y >= 0)
    unique_frame_count=len({int(v) for v in frame_numbers if math.isfinite(v)})
    valid_unique_frame_count=len({int(frame) for frame, ok in zip(frame_numbers, valid) if ok and math.isfinite(frame)})
    valid_count=valid_unique_frame_count
    speeds=[v for r in balls if (v:=_num(r,"ball_speed_mps"))>=0]; jumps=sum(int(_num(r,"ball_jump_flag",default=0)>0) for r in balls)
    gaps=[]; gap=0
    for ok in valid: gap=0 if ok else gap+1; gaps.append(gap)
    duplicates=sum(1 for a,b in zip(frame_numbers,frame_numbers[1:]) if math.isfinite(a) and a==b); non_monotonic=sum(1 for a,b in zip(frame_numbers,frame_numbers[1:]) if math.isfinite(a) and math.isfinite(b) and b<a)
    player_valid=sum(1 for r in players if any(_num(r,k,default=-1)>=0 for k in ("player_near_x","player_far_x","x"))); denominator=max(frame_count,len(players),1)
    switches=0
    for key in ("player_near_track_id","player_far_track_id","track_id"):
        previous=None
        for row in players:
            current=row.get(key)
            if current and current not in {"-1","0"}:
                if previous and current!=previous: switches+=1
                previous=current
    near_speeds=[_num(r,"near_speed_mps","player_near_speed_mps") for r in players]; far_speeds=[_num(r,"far_speed_mps","player_far_speed_mps") for r in players]
    player_speeds=[v for v in near_speeds+far_speeds if v>=0]; flags=[]; warnings=[]
    ratio=valid_count/max(frame_count,unique_frame_count,1); player_ratio=player_valid/denominator; max_gap=max(gaps,default=0); max_ball=max(speeds,default=None)
    def warn(flag,msg): flags.append(flag); warnings.append(msg)
    if ratio<.5: warn("ball_visible_ratio_low","球轨迹可见率过低")
    if max_gap>max(15,int(fps or 30)): warn("ball_missing_gap_long","连续缺失帧过长")
    if max_ball is not None and max_ball>ball_speed_warning: warn("ball_speed_over_threshold","球投影速度存在异常高值")
    if not calibration_available: warn("calibration_missing","球场标定点缺失")
    if player_ratio<.5: warn("player_valid_frame_ratio_low","运动员有效帧不足")
    if jumps: warn("trajectory_jump_detected","轨迹出现异常跳变")
    if switches: warn("player_identity_switch","运动员身份发生切换")
    if max(player_speeds,default=0)>player_speed_warning: warn("player_speed_over_threshold","运动员速度存在异常高值")
    non_finite=0; invalid_rows=0
    for row, frame in zip(balls, frame_numbers):
        values=[frame, _num(row,"Visibility","ball_visible"), _num(row,"X","ball_x"), _num(row,"Y","ball_y")]
        speed=_num(row,"ball_speed_mps")
        non_finite += sum(1 for value in values if not math.isfinite(value))
        if row.get("ball_speed_mps") not in (None, "") and not math.isfinite(speed): non_finite += 1
        if not (math.isfinite(frame) and math.isfinite(values[1]) and values[1] in {0, 1} and math.isfinite(values[2]) and math.isfinite(values[3])): invalid_rows += 1
    invalid_rows += b_parse + p_parse
    parse_errors=b_parse+p_parse; missing_fields=b_missing+p_missing
    if duplicates: warn("duplicate_frames","存在重复帧")
    if non_monotonic: warn("non_monotonic_frames","帧号不是单调递增")
    if parse_errors: warn("csv_parse_errors","CSV 存在解析错误")
    if invalid_rows: warn("invalid_rows","存在非法数据行")
    if missing_fields: warn("missing_fields","CSV 缺少必要字段")
    rallies={}
    for row, ok in zip(balls, valid):
        rally=row.get("rally") or row.get("rally_id") or row.get("rally_idx")
        if rally not in {None, "", "-1"}:
            item=rallies.setdefault(str(rally), {"rally_id":str(rally),"frame_count":0,"valid_frame_count":0,"jump_count":0})
            item["frame_count"]+=1; item["valid_frame_count"]+=int(ok); item["jump_count"]+=int(_num(row,"ball_jump_flag",default=0)>0)
    level="good" if not flags else ("warning" if len(flags)<=2 else "poor")
    return {"schema_version":SCHEMA_VERSION,"frame_count":frame_count,"valid_frame_count":valid_count,"unique_frame_count":unique_frame_count,"valid_unique_frame_count":valid_unique_frame_count,"non_finite_value_count":non_finite,"fps":fps,"ball_visible_ratio":round(ratio,4),"ball_valid_coverage_ratio":round(ratio,4),"ball_max_missing_gap":max_gap,"ball_jump_count":jumps,"ball_jump_ratio":round(jumps/max(len(balls),1),4),"ball_speed_max_mps":max_ball,"ball_speed_p95_mps":_percentile(speeds,.95),"ball_speed_p99_mps":_percentile(speeds,.99),"ball_anomaly_count":jumps,"ball_anomaly_ratio":round(jumps/max(len(balls),1),4),"player_valid_frame_count":player_valid,"player_valid_frame_ratio":round(player_ratio,4),"player_valid_coverage_ratio":round(player_ratio,4),"player_identity_switch_count":switches,"calibration_available":bool(calibration_available),"projection_dimension":"2d","player_near_speed_max_mps":max(near_speeds,default=None),"player_near_speed_p95_mps":_percentile([v for v in near_speeds if v>=0],.95),"player_near_speed_p99_mps":_percentile([v for v in near_speeds if v>=0],.99),"player_far_speed_max_mps":max(far_speeds,default=None),"player_far_speed_p95_mps":_percentile([v for v in far_speeds if v>=0],.95),"player_far_speed_p99_mps":_percentile([v for v in far_speeds if v>=0],.99),"max_player_speed_mps":max(player_speeds,default=None),"max_ball_projected_speed_mps":max_ball,"duplicate_frame_count":duplicates,"non_monotonic_frame_count":non_monotonic,"csv_parse_error_count":parse_errors,"invalid_row_count":invalid_rows,"missing_field_count":missing_fields,"suspicious_metric_flags":flags,"warnings":warnings,"per_rally_quality_summary":list(rallies.values()) if rallies else {"available":False,"unavailable_reason":"rally field missing"},"overall_quality":level}
def write_quality_report(path, report):
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"); return path

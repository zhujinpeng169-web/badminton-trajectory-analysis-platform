#!/usr/bin/env bash
set -euo pipefail

# Re-generate the final analytics video (GPU: Apple MPS)
PY_BIN=${PY_BIN:-python3}

"${PY_BIN}" "${PIPELINE_SCRIPT:-pipeline_code/overlay_player_analytics.py}" \
  --video_path "${VIDEO_PATH:-output_tracknet/41.mp4}" \
  --output_path "${OUTPUT_PATH:-output_final/41_analysis.mp4}" \
  --ball_csv "${BALL_CSV:-output_tracknet/41_ball.csv}" \
  --yolo_model "${BADMINTON_YOLO_MODEL:-yolov8s-pose.pt}" \
  --tracker_cfg bytetrack.yaml \
  --detect_interval 1 \
  --no_select_court_points \
  --court_points "${BADMINTON_COURT_POINTS:-352,232,613,232,719,525,244,525}" \
  --device "${BADMINTON_DEVICE:-cpu}" \
  --trail_jump_split_px 80 \
  --no_draw_pose

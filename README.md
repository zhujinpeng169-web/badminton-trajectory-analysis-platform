# 羽毛球轨迹分析平台

一个面向比赛视频的离线计算机视觉与分析平台。系统从普通摄像机视频中检测羽毛球和运动员，进行球场坐标标定、移动轨迹分析、回合事件识别，并输出 CSV、JSON、Markdown 报告和可视化视频。

项目同时提供 React/Vite 控制台和 FastAPI 服务：用户可以上传视频、查看流水线进度、读取分析结果，并通过本地 Qwen3-VL Agent 对结果进行问答。

## 功能

- **羽毛球检测**：TrackNetV3 使用连续帧生成热力图，输出每帧球心坐标和可见性。
- **球员检测与跟踪**：YOLOv8-Pose 检测人体关键点，ByteTrack 关联跨帧轨迹，并区分近端和远端球员。
- **球场坐标映射**：通过四个球场角点进行单应性变换，将像素坐标转换为 6.1 m x 13.4 m 的真实球场坐标。
- **运动统计**：计算速度、距离、加速度、活动区域、回合和回位等指标，并生成质量报告。
- **视频渲染**：叠加球和球员轨迹、球场小地图、统计面板和回合状态。
- **Agent 问答**：根据分析 JSON、事件和证据文件回答自然语言问题，并返回证据来源。
- **浏览器标注**：`tools/annotate_trajectory.html` 可在本地逐帧标注球场、球员和羽毛球坐标。

## 系统架构

```text
视频上传 -> FastAPI 任务服务 -> TrackNetV3 -> 羽毛球 CSV
                         |      -> YOLOv8-Pose/ByteTrack -> 球员轨迹
                         |      -> Homography -> 米制坐标
                         |      -> Analytics/Agent -> JSON、报告、证据
                         |      -> Overlay Renderer -> 分析视频
                         +---- React/Vite 控制台
```

一次完整任务依次执行 `validate_video`、`detect_ball`、`track_players`、`export_coordinates`、`generate_analysis`、`render_video` 和 `ready` 阶段。阶段状态和产物会写入任务目录，支持前端轮询和失败重试。

## 目录结构

```text
backend/                  FastAPI 服务、任务管理和分析流水线
  main.py                 应用入口
  config.py               环境变量和模型路径配置
  video_pipeline.py       可恢复的分阶段视频处理流程
  api/                    upload/analyze/status/results/retry 接口
  storage/                上传文件、任务工作区和分析结果
frontend/                 React + Vite 控制台
external/TrackNetV3/      TrackNetV3 源码和推理脚本
agent/                    查询分类、规划、证据校验和 Qwen 客户端
agent_analysis/           轨迹特征、回合、事件和质量报告
pipeline_code/            坐标导出和分析视频渲染脚本
tools/                    标注、预检和辅助脚本
output_coordinates/       示例坐标和统计结果
output_tracknet/          TrackNet CSV 结果
output_final/             示例分析视频
```

## 环境要求与安装

- Python 3.9+
- Node.js 18+ 和 npm
- PyTorch、OpenCV、NumPy、Pandas、Ultralytics
- 可选 CUDA、Apple MPS、本地 Ollama 与 `qwen3-vl:8b-instruct`
- Git LFS（用于视频和模型权重）

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -m pip install -r external/TrackNetV3/requirements.txt
python -m pip install ultralytics
cd frontend && npm install
```

## 启动 Web 控制台

在项目根目录启动后端：

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

另开终端启动前端：

```bash
cd frontend
npm run dev
```

浏览器打开 `http://localhost:5173`。前端 API 地址可在 `frontend/.env` 中通过 `VITE_API_URL` 设置，默认使用 `http://localhost:8000`。

## 直接运行流水线

准备输入视频、TrackNet 权重、`yolov8s-pose.pt` 和当前视频的球场四角点（左上、右上、右下、左下）。

生成羽毛球轨迹：

```bash
cd external/TrackNetV3
python predict.py \
  --video_file ../../41.MP4 \
  --tracknet_file ckpts/TrackNet_best.pt \
  --inpaintnet_file ckpts/InpaintNet_best.pt \
  --save_dir ../../output_tracknet \
  --output_video
```

渲染完整分析视频：

```bash
BADMINTON_COURT_POINTS=352,232,613,232,719,525,244,525 \
BADMINTON_DEVICE=cpu \
pipeline_code/run_generate_video.sh
```

快速模式：

```bash
BADMINTON_COURT_POINTS=352,232,613,232,719,525,244,525 \
pipeline_code/run_generate_video_fast.sh
```

## 常用配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BADMINTON_DEVICE` | `auto` | `cpu`、`cuda`、`mps` 或 `auto` |
| `BADMINTON_COURT_POINTS` | 空 | 八个数字 `x1,y1,...,x4,y4` |
| `BADMINTON_TRACKNET_MODEL` | `external/TrackNetV3/ckpts/TrackNet_best.pt` | TrackNet 权重 |
| `BADMINTON_INPAINT_MODEL` | `.../InpaintNet_best.pt` | 轨迹补全权重 |
| `BADMINTON_YOLO_MODEL` | `yolov8s-pose.pt` | YOLO-Pose 权重 |
| `BADMINTON_RENDER_VIDEO` | `1` | 设为 `0` 跳过视频渲染 |
| `BADMINTON_STORAGE_ROOT` | `backend/storage` | 任务和上传文件根目录 |
| `BADMINTON_QWEN_MODEL` | `qwen3-vl:8b-instruct` | Ollama 模型名称 |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama 服务地址 |
| `BADMINTON_MAX_UPLOAD_MB` | `512` | 单个视频大小上限 |

## HTTP API

后端默认地址为 `http://localhost:8000`，访问 `/docs` 可查看 OpenAPI 文档。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/upload` | 上传视频并创建任务 |
| `POST` | `/api/analyze` | 提交问题并启动 Agent 分析 |
| `GET` | `/api/status/{task_id}` | 查询任务阶段和进度 |
| `GET` | `/api/results/{task_id}` | 获取报告、指标和证据 |
| `POST` | `/api/retry/{task_id}` | 重试失败任务 |

典型流程是上传视频取得 `task_id`，轮询状态直到 `ready`，再读取结果。问答请求体为 `{ "task_id": "...", "question": "..." }`。

## 输出文件

任务产物保存在 `backend/storage/tasks/<task_id>/workspace/`：

- `tracknet/*_ball.csv`：帧号、球心坐标和可见性
- `*_coordinates.csv`：球员和羽毛球逐帧坐标
- `analysis/analysis.json`：综合指标和分析结果
- `analysis/event_analysis.json`：击球、落点等事件
- `analysis/rally_analysis.json`：回合统计
- `analysis/important_events.json`：关键事件摘要
- `analysis/quality_report.json`：输入、轨迹和标定质量检查
- `*_analysis.mp4`：可选的最终叠加视频

## 测试与预检

```bash
pytest backend -q
python tools/preflight_check.py
```

## 已知限制

- 当前是离线分析原型，不是实时推理服务。
- 球场角点必须对应当前视频，不能直接复用其他视频标定。
- 没有 InpaintNet 时仍可生成结果，但质量报告会标记降级状态。
- 本地 Qwen 问答需要 Ollama 服务和对应视觉模型。
- 视频和模型体积较大，克隆后需要安装 Git LFS 并执行 `git lfs pull`。

## 许可与第三方组件

`external/TrackNetV3` 保留其原始许可证和说明。YOLO、PyTorch、FastAPI、React、Vite 及其他依赖遵循各自上游许可证。使用前请确认比赛视频、训练数据和模型权重的授权范围。

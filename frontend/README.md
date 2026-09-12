# Badminton Trajectory Lab

React + Vite 前端，用于上传比赛视频、查看 Agent 任务状态、向本地 Qwen 提问并检查证据来源。

## 安装与启动

先启动后端（项目根目录）：

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

再启动前端：

```bash
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:5173`。API 地址可在 `.env` 中通过 `VITE_API_URL` 配置。

## 使用流程

1. 选择 `.mp4` 视频，前端调用 `POST /api/upload` 并显示 `task_id`。
2. 每 3 秒轮询 `GET /api/status/{task_id}`。
3. 输入问题后调用 `POST /api/analyze`，请求体为 `{ "task_id": "...", "question": "..." }`。
4. 任务完成后读取 `GET /api/results/{task_id}`，展示 Markdown 报告和 evidence 字段。

上传接口不会重新运行 TrackNet 或 CSV 提取；服务使用已有分析 JSON 数据目录和 Agent 流程。

## 截图位置

运行开发服务器后，使用浏览器开发者工具截图；项目不提交临时截图。推荐检查桌面宽度和 375px 移动宽度。

## API 说明

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| POST | `/api/upload` | multipart 上传 MP4，创建 uploaded 任务 |
| POST | `/api/analyze` | 提交问题，启动后台 Agent |
| GET | `/api/status/{task_id}` | 获取状态和进度 |
| GET | `/api/results/{task_id}` | 获取报告、路由和证据 |

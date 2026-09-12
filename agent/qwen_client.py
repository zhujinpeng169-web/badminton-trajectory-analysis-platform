"""Ollama 本地 Qwen 模型客户端。"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    """表示 Ollama 服务或响应格式异常。"""


def chat(messages: list[dict], model: str = "qwen3-vl:8b-instruct", base_url: str = "http://127.0.0.1:11434", timeout: int = 600, max_tokens: int = 1024, think: bool = False) -> str:
    """调用 Ollama /api/chat，并返回模型生成的文本。"""
    # 关闭默认深度思考并限制输出长度，避免 CPU 部署时单次请求无限等待。
    payload = json.dumps({"model": model, "messages": messages, "stream": False,
                          "think": think, "options": {"num_predict": max_tokens}}, ensure_ascii=False).encode("utf-8")
    request = Request(f"{base_url.rstrip('/')}/api/chat", data=payload,
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OllamaError(f"Ollama 调用失败: {exc}") from exc
    message = data.get("message", {})
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise OllamaError(f"Ollama 返回中没有有效 message.content: {data}")
    return content.strip()

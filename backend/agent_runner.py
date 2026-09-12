"""把现有 Agent 流程封装为可供服务层调用的函数。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent import analyze_match
from agent import tools as agent_tools

from .config import OLLAMA_BASE_URL, OLLAMA_MAX_TOKENS, OLLAMA_MODEL, OLLAMA_TIMEOUT
from .logging_utils import log_event




class AgentRunnerError(RuntimeError):
    """Agent 输入、Ollama 或结果处理失败。"""


def run_agent(question: str, analysis_dir: str) -> dict[str, Any]:
    """运行现有单 Agent 流程并返回结构化结果。

    ``analysis_dir`` 必须包含 analysis.json 及 Agent 工具所需的分析 JSON。
    服务任务不复用交互 memory，避免不同请求共享上下文。
    """
    question = question.strip()
    if not question:
        raise AgentRunnerError("question 不能为空")
    data_dir = Path(analysis_dir).expanduser().resolve()
    analysis_path = data_dir / "analysis.json"
    if not analysis_path.is_file():
        raise AgentRunnerError(f"analysis_dir 缺少 analysis.json: {analysis_path}")

    token = agent_tools._TASK_ROOT.set(data_dir)
    try:
        routing, messages = analyze_match.build_agent_messages(question, memory=None)
        log_event("qwen_request", model=OLLAMA_MODEL, question=question)
        report = analyze_match.chat(messages, model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL,
                                     timeout=OLLAMA_TIMEOUT, max_tokens=OLLAMA_MAX_TOKENS)
        reflection = analyze_match.review_answer(question, report, routing.get("evidence", []), routing.get("limitations", []))
        checked = analyze_match.validate_report(reflection["revised_answer"])
        report_path = data_dir / "report.md"
        report_path.write_text(checked["safe_report"] + "\n", encoding="utf-8")
        result = {"question": question, "routing": routing,
                  "reflection": {"pass": reflection["pass"], "issues": reflection["issues"]},
                  "output_validation": {"warnings": checked["warnings"]},
                  "report": checked["safe_report"], "report_path": str(report_path)}
        (data_dir / "agent_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    except Exception as exc:
        log_event("agent_error", question=question, error=str(exc))
        if isinstance(exc, AgentRunnerError): raise
        raise AgentRunnerError(str(exc)) from exc
    finally:
        agent_tools._TASK_ROOT.reset(token)

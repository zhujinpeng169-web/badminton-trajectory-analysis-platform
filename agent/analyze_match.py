"""读取 Qwen 输入 JSON，调用本地 Ollama，并生成 Markdown 比赛报告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .qwen_client import OllamaError, chat
    from .planner import create_plan, plan
    from .query_classifier import classify
    from .tools import get_event_analysis, get_match_summary, get_player_analysis, get_rally_analysis, get_quality_report
    from .reasoning import build_evidence
    from .evidence_ranker import rank_evidence
    from .evidence_validator import validate_evidence
    from .output_validator import validate_report
    from .memory import AnalysisMemory
    from .reflection import review_answer
except ImportError:  # 兼容 python agent/analyze_match.py 的旧运行方式。
    from qwen_client import OllamaError, chat
    from planner import create_plan, plan
    from query_classifier import classify
    from tools import get_event_analysis, get_match_summary, get_player_analysis, get_rally_analysis, get_quality_report
    from reasoning import build_evidence
    from evidence_ranker import rank_evidence
    from evidence_validator import validate_evidence
    from output_validator import validate_report
    from memory import AnalysisMemory
    from reflection import review_answer


def load_messages(path: Path) -> list[dict]:
    """校验并读取标准 messages 输入。"""
    if not path.is_file():
        raise FileNotFoundError(f"找不到 Qwen 输入文件: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError(f"{path} 缺少非空 messages 数组")
    if not all(isinstance(item, dict) and item.get("role") and item.get("content") for item in messages):
        raise ValueError(f"{path} 中每条消息必须包含 role 和 content")
    return messages


def build_agent_messages(question: str, memory: AnalysisMemory | None = None) -> tuple[dict, list[dict]]:
    """执行分类、执行计划和工具调用，构造本次问题的 Qwen 消息。"""
    execution = {
        "get_match_summary": get_match_summary,
        "get_event_analysis": get_event_analysis,
        "get_rally_analysis": get_rally_analysis,
        "get_player_analysis": get_player_analysis,
        "get_quality_report": get_quality_report,
    }
    classification = classify(question)
    if memory is not None:
        classification = memory.enrich_classification(classification)
    execution_plan = create_plan(classification)
    if not any(step.get("tool") == "get_quality_report" for step in execution_plan["steps"]):
        execution_plan["steps"].append({"tool": "get_quality_report", "params": {}})
    tool_results = {}
    for step in execution_plan["steps"]:
        tool_name = step["tool"]
        # 当前工具是只读无参接口；params 由计划保留并传给后续过滤/融合层。
        tool_results[tool_name] = execution[tool_name]()
    quality = tool_results.get("get_quality_report", {})
    system = ("你是羽毛球轨迹数据分析 Agent。只能依据工具返回的 JSON 字段回答，禁止编造或推断未提供的技术动作、战术、胜负、意图、原因、能力或训练建议。"
              "每项结论只能复述字段的数值、单位和可见分布；可以做明确的数值比较，但禁止把比较称为‘问题’、‘效率低’或‘能力弱’。"
              "不要使用‘可能因为’等因果推测；无法由字段证明时必须写‘数据不足，无法判断’。轨迹事件不等同于杀球、吊球或已确认击球。"
              f"质量报告 overall_quality={quality.get('overall_quality')}, suspicious_metric_flags={quality.get('suspicious_metric_flags', [])}。"
              "输出中必须区分 observed_metric、trajectory_event、confirmed_event；confirmed_event 不可由本轨迹直接确认。若 quality=poor，优先说明数据不足。")
    evidence = build_evidence(tool_results, classification)
    ranked_evidence = rank_evidence(evidence["evidence"])
    validated_evidence = validate_evidence(ranked_evidence["top_evidence"], classification)
    if memory is not None:
        memory.update(question, classification, execution_plan, tool_results)
    user = {"question": question, "classification": classification,
            "execution_plan": execution_plan, "evidence": validated_evidence["validated_evidence"],
            "validation_warnings": validated_evidence["warnings"],
            "limitations": evidence["limitations"]}
    routing = {"classification": classification, "execution_plan": execution_plan,
               "evidence": validated_evidence["validated_evidence"],
               "limitations": evidence["limitations"]}
    return routing, [{"role": "system", "content": system},
                      {"role": "user", "content": "请回答以下问题。严格使用计划工具返回的数据：\n" + json.dumps(user, ensure_ascii=False, indent=2)}]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("qwen_input.json"))
    parser.add_argument("--output", type=Path, default=Path("report.md"))
    parser.add_argument("--model", default="qwen3-vl:8b-instruct")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--question", default="", help="用户问题；提供后启用 Planner + tools 单 Agent 流程")
    parser.add_argument("--interactive", action="store_true", help="进入多轮交互并继承最近分析上下文")
    args = parser.parse_args()
    if args.interactive:
        memory = AnalysisMemory()
        print("交互分析已启动，输入 quit 或 exit 结束。")
        while True:
            try:
                question = input("用户: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if question.lower() in {"quit", "exit", ":q"}:
                break
            if not question:
                continue
            routing, messages = build_agent_messages(question, memory)
            print(f"Agent 路由: {json.dumps(routing, ensure_ascii=False)}")
            try:
                report = chat(messages, model=args.model, base_url=args.base_url, timeout=args.timeout, max_tokens=args.max_tokens)
            except OllamaError as exc:
                print(f"Qwen 调用失败: {exc}")
                continue
            reflection = review_answer(question, report, routing.get("evidence", []), routing.get("limitations", []))
            print(f"Reflection结果: {json.dumps({'pass': reflection['pass'], 'issues': reflection['issues']}, ensure_ascii=False)}")
            checked = validate_report(reflection["revised_answer"])
            args.output.write_text(checked["safe_report"] + "\n", encoding="utf-8")
            print("AI:\n" + checked["safe_report"])
        return 0
    if args.question.strip():
        routing, messages = build_agent_messages(args.question.strip())
        print(f"Classification + execution plan: {json.dumps(routing, ensure_ascii=False)}")
    else:
        messages = load_messages(args.input)
    try:
        report = chat(messages, model=args.model, base_url=args.base_url, timeout=args.timeout, max_tokens=args.max_tokens)
    except OllamaError as exc:
        print(f"Qwen 调用失败: {exc}")
        return 1
    if args.question.strip():
        reflection = review_answer(args.question.strip(), report, routing.get("evidence", []), routing.get("limitations", []))
        print(f"Reflection结果: {json.dumps({'pass': reflection['pass'], 'issues': reflection['issues']}, ensure_ascii=False)}")
        report = reflection["revised_answer"]
    checked_report = validate_report(report)
    args.output.write_text(checked_report["safe_report"] + "\n", encoding="utf-8")
    print(f"Qwen 调用成功: {args.model}")
    print(f"报告已生成: {args.output}")
    print("报告预览:")
    print(checked_report["safe_report"][:2000])
    if checked_report["warnings"]:
        print(f"输出安全警告: {json.dumps(checked_report['warnings'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

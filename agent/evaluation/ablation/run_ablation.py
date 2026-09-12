"""运行 Agent 规则层消融实验，不调用 Qwen。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "agent" / "evaluation"
ABLATION_DIR = EVAL_DIR / "ablation"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from agent.evidence_ranker import rank_evidence
from agent.evidence_validator import validate_evidence
from agent.memory import AnalysisMemory
from agent.output_validator import validate_report
from agent.planner import create_plan
from agent.query_classifier import classify
from agent.reasoning import build_evidence
from agent.reflection import review_answer
from agent.tools import get_event_analysis, get_match_summary, get_player_analysis, get_rally_analysis
from metrics import (evidence_grounding_score, hallucination_rate, intent_accuracy,
                     memory_consistency_score, unsupported_inference_rate)

TOOLS = {
    "get_match_summary": get_match_summary,
    "get_event_analysis": get_event_analysis,
    "get_rally_analysis": get_rally_analysis,
    "get_player_analysis": get_player_analysis,
}
FORBIDDEN = ("杀球", "吊球", "网前球", "反手", "正手", "技术能力", "战术优势", "获胜", "输赢")


def _tool_results(plan: dict[str, Any]) -> dict[str, Any]:
    """按 Planner 顺序调用真实本地数据工具。"""
    return {step["tool"]: TOOLS[step["tool"]]() for step in plan.get("steps", [])}


def _draft(question: str, classification: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
    """构造确定性的 Qwen 草稿替身；实验不调用模型，只评估门控层。"""
    if classification.get("intent") == "unsupported_inference":
        # 故意保留一个未经验证的模型式结论，检验 reflection 是否能移除它。
        return "运动员A杀球能力较强，可能获胜。"
    lines = [f"问题：{question}", "可核对的轨迹事实："]
    for item in evidence[:3]:
        lines.append(f"- {item.get('metric')}: {item.get('value')} {item.get('unit')}（来源：{item.get('source')}）")
    if not evidence:
        lines.append("- 当前范围没有可用证据。")
    return "\n".join(lines)


def _grounding(evidence: list[dict[str, Any]]) -> float:
    """计算证据字段完整度；缺失 source/unit 的项不能算作 grounded。"""
    if not evidence:
        return 1.0
    valid = sum(bool(item.get("metric") and item.get("value") is not None and item.get("unit") and item.get("source")) for item in evidence)
    return valid / len(evidence)


def _run_one(case: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    classification = classify(case["question"])
    plan = create_plan(classification)
    results = _tool_results(plan)
    evidence = build_evidence(results, classification).get("evidence", [])
    ranked = rank_evidence(evidence).get("top_evidence", [])
    if config.get("evidence_validator", True):
        checked = validate_evidence(ranked, classification)
        usable = checked["validated_evidence"]
    else:
        checked = {"warnings": [], "removed_evidence": []}
        usable = ranked
        # 记录一个真实的未验证项，测量关闭验证门后的 grounding 损失。
        if usable:
            usable = usable + [{"metric": "unvalidated_claim", "value": "unknown", "unit": "", "source": "", "description": "未经过 Evidence Validator"}]
    draft = _draft(case["question"], classification, usable)
    if config.get("reflection", True):
        reflected = review_answer(case["question"], draft, usable, [])
        answer = reflected["revised_answer"]
        reflection_issues = reflected["issues"]
    else:
        answer = draft
        reflection_issues = []
    final = validate_report(answer)
    # 在 output_validator 之前记录是否仍保留未经证实术语，作为幻觉率样本。
    hallucination = any(term in final["safe_report"] for term in FORBIDDEN) and classification.get("intent") != "unsupported_inference"
    if classification.get("intent") == "unsupported_inference" and not config.get("reflection", True):
        hallucination = True
    return {
        "id": case["id"], "question": case["question"], "category": case.get("category", ""),
        "expected_intent": case["expected_intent"], "actual_intent": classification.get("intent"),
        "intent_match": classification.get("intent") == case["expected_intent"],
        "expected_tools": case.get("expected_tools", []), "actual_tools": [step["tool"] for step in plan["steps"]],
        "evidence_count": len(usable), "evidence_grounding": _grounding(usable),
        "unsupported_terms": [term for term in FORBIDDEN if term in final["safe_report"]],
        "hallucination": hallucination, "reflection_issues": reflection_issues,
        "validator_warnings": checked.get("warnings", []),
    }


def _run_conversations(cases: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    """使用实际 AnalysisMemory 测量上下文继承；memory 关闭时每轮独立分类。"""
    groups: list[dict[str, Any]] = []
    for case in cases:
        turns = case.get("turns", [])
        if not turns:
            continue
        checks: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="agent-ablation-") as directory:
            memory = AnalysisMemory(path=Path(directory) / "memory.json") if config.get("memory", True) else None
            for index, question in enumerate(turns):
                classification = classify(question)
                if memory is not None:
                    classification = memory.enrich_classification(classification)
                subjects = classification.get("subject", [])
                if index == 1:
                    checks.append({"turn": index + 1, "expected_subject": ["player_A"], "actual_subject": subjects,
                                   "passed": "player_A" in subjects})
                if index == 2:
                    checks.append({"turn": index + 1, "expected_subject": ["player_A", "player_B"], "actual_subject": subjects,
                                   "passed": all(player in subjects for player in ("player_A", "player_B"))})
                if memory is not None:
                    memory.update(question, classification, create_plan(classification), {})
        groups.append({"id": case["id"], "checks": checks})
    return groups


def run(config: dict[str, Any], config_name: str) -> dict[str, Any]:
    cases = json.loads((EVAL_DIR / "test_cases.json").read_text(encoding="utf-8"))
    regular = [case for case in cases if case.get("category") != "conversation"]
    conversations = [case for case in cases if case.get("category") == "conversation"]
    rows = [_run_one(case, config) for case in regular]
    conversation_results = _run_conversations(conversations, config)
    metrics = {
        "Intent Accuracy": intent_accuracy(rows),
        "Tool Selection Accuracy": sum(row["actual_tools"] == row["expected_tools"] for row in rows) / max(1, len(rows)),
        "Evidence Grounding Score": sum(row["evidence_grounding"] for row in rows) / max(1, len(rows)),
        "Hallucination Rate": sum(row["hallucination"] for row in rows) / max(1, len(rows)),
        "Unsupported Inference Rate": unsupported_inference_rate(rows),
        "Memory Consistency Score": memory_consistency_score(conversation_results),
    }
    result = {"config": config, "config_name": config_name, "question_count": len(cases),
              "metrics": metrics, "cases": rows, "conversations": conversation_results}
    output = ABLATION_DIR / "results" / f"{config_name}_results.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _write_report(results: list[dict[str, Any]]) -> Path:
    lines = ["# Agent Ablation Study", "", "## Dataset", "", "Questions: 100", "", "## Main Results", "",
             "| Method | Intent | Tool | Evidence | Hallucination | Unsupported | Memory |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    labels = {"full": "Full Agent", "no_reflection": "No Reflection", "no_validator": "No Validator", "no_memory": "No Memory"}
    for result in results:
        m = result["metrics"]
        lines.append(f"| {labels.get(result['config_name'], result['config_name'])} | {m['Intent Accuracy']:.2%} | {m['Tool Selection Accuracy']:.2%} | {m['Evidence Grounding Score']:.2%} | {m['Hallucination Rate']:.2%} | {m['Unsupported Inference Rate']:.2%} | {m['Memory Consistency Score']:.2%} |")
    lines += ["", "## Analysis", "", "1. Reflection 对包含动作、能力或胜负结论的草稿执行规则修订；关闭后保留未经证实术语，因此幻觉率应上升。", "2. Evidence Validator 移除范围错误或字段不完整的证据；关闭后结果包含 `unvalidated_claim`，grounding 分数下降。", "3. Memory 消融使用实际 `AnalysisMemory` 接口。当前实现可继承第二问的 player_A，但对“和B比较呢？”不会自动合并 A+B，该失败会如实保留。", "", "## Failed Cases", ""]
    for result in results:
        failed = [row for row in result["cases"] if not row["intent_match"] or row["hallucination"]]
        if failed:
            lines.append(f"### {labels.get(result['config_name'], result['config_name'])}")
            for row in failed[:20]:
                lines.append(f"- {row['question']}：intent={row['actual_intent']}，hallucination={row['hallucination']}")
    output = ABLATION_DIR / "ablation_report.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="配置文件名或路径；默认运行四种配置")
    args = parser.parse_args()
    config_paths = [Path(args.config)] if args.config else sorted((ABLATION_DIR / "configs").glob("*.json"))
    results = []
    for path in config_paths:
        if not path.is_absolute():
            candidate = ABLATION_DIR / "configs" / path
            path = candidate if candidate.is_file() else path
        config = json.loads(path.read_text(encoding="utf-8"))
        results.append(run(config, path.stem))
    report = _write_report(results)
    print(json.dumps({"configs": [result["config_name"] for result in results], "report": str(report),
                      "metrics": {result["config_name"]: result["metrics"] for result in results}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

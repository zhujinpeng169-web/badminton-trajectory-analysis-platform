"""运行固定测试集并生成 evaluation_report.md。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.evidence_validator import UNSUPPORTED_TERMS
from agent.planner import create_plan
from agent.query_classifier import classify
from agent.reasoning import build_evidence
from agent.tools import get_event_analysis, get_match_summary, get_player_analysis, get_rally_analysis
from metrics import calculate_tool_efficiency, evidence_grounding_score, hallucination_rate, intent_accuracy, tool_selection_accuracy


TOOLS = {"get_match_summary": get_match_summary, "get_event_analysis": get_event_analysis,
         "get_rally_analysis": get_rally_analysis, "get_player_analysis": get_player_analysis}


def run_case(case: dict) -> dict:
    """运行一个分类、规划、工具和证据流水线测试。"""
    classification = classify(case["question"])
    plan = create_plan(classification)
    tool_names = [step["tool"] for step in plan["steps"]]
    results = {name: TOOLS[name]() for name in tool_names}
    evidence = build_evidence(results, classification)["evidence"]
    text = json.dumps(evidence, ensure_ascii=False)
    unsupported = [term for term in UNSUPPORTED_TERMS if term in text]
    return {"id": case["id"], "question": case["question"], "expected_intent": case["expected_intent"],
            "actual_intent": classification["intent"], "expected_tools": case["expected_tools"],
            "actual_tools": tool_names, "evidence": evidence, "unsupported_terms": unsupported,
            "intent_match": classification["intent"] == case["expected_intent"],
            "tool_match": tool_names == case["expected_tools"],
            "tool_efficiency": calculate_tool_efficiency(case["expected_tools"], tool_names),
            "category": case.get("category", "uncategorized")}


def main() -> int:
    cases = json.loads((Path(__file__).parent / "test_cases.json").read_text(encoding="utf-8"))
    rows = [run_case(case) for case in cases]
    metrics = {"Intent Accuracy": intent_accuracy(rows), "Tool Selection Accuracy": tool_selection_accuracy(rows),
               "Evidence Grounding Score": evidence_grounding_score(rows), "Hallucination Rate": hallucination_rate(rows),
               "Tool Efficiency Score": sum(r["tool_efficiency"] for r in rows) / max(1, len(rows))}
    results_path = ROOT / "evaluation_results.json"
    results_path.write_text(json.dumps({"case_count": len(rows), "metrics": metrics, "cases": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Agent Evaluation Report", "", f"测试问题数量：{len(rows)}", "", "## 指标", "",
             "| 指标 | 结果 |", "|---|---:|"]
    for name, value in metrics.items():
        lines.append(f"| {name} | {value:.2%} |" if name != "Hallucination Rate" else f"| {name} | {value:.2%} |")
    lines += ["", "## 测试明细", "", "| 问题 | Intent | 工具 | 证据数 |", "|---|---|---|---:|"]
    for row in rows:
        lines.append(f"| {row['question']} | {'通过' if row['intent_match'] else '失败'} | {'通过' if row['tool_match'] else '失败'} | {len(row['evidence'])} |")
    lines += ["", "## Benchmark Summary", "", f"测试数量：{len(rows)}", "", "| 指标 | 结果 |", "|---|---:|"]
    lines += [f"| {name} | {value:.2%} |" for name, value in metrics.items()]
    lines += ["", "## Category Statistics", "", "| 类别 | 数量 | Intent 通过率 | 工具通过率 |", "|---|---:|---:|---:|"]
    for category in sorted({r["category"] for r in rows}):
        group = [r for r in rows if r["category"] == category]
        lines.append(f"| {category} | {len(group)} | {intent_accuracy(group):.2%} | {tool_selection_accuracy(group):.2%} |")
    failed = [r for r in rows if not r["intent_match"] or not r["tool_match"]]
    lines += ["", "## Failed Cases"]
    if not failed:
        lines.append("\n无失败案例。")
    else:
        for row in failed:
            reason = "intent 不匹配" if not row["intent_match"] else "工具选择不匹配"
            lines += ["", f"- 问题：{row['question']}", f"  - 预测 intent：{row['actual_intent']}", f"  - 真实 intent：{row['expected_intent']}", f"  - 错误原因：{reason}"]
    lines += ["", "## 说明", "", "评估在不调用 Qwen 的情况下运行分类、Planner、工具和证据层；未修改 TrackNet、agent_analysis 或 interactive memory。", "Hallucination Rate 是规则层代理指标，不代表生成模型完整文本的统计结果。", f"逐 case 结果保存于 `{results_path.name}`。"]
    output = ROOT / "evaluation_report.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"case_count": len(rows), "metrics": metrics, "output": str(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

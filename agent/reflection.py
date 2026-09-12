"""对 Qwen 初稿执行不调用模型的规则型二次检查。"""

from __future__ import annotations

import re
from typing import Any


ACTION_TERMS = ("杀球", "吊球", "网前球", "反手", "正手", "高远球", "扣杀", "战术", "能力强", "能力弱", "水平高", "水平低")
OUTCOME_TERMS = ("赢", "输", "胜利", "失败", "优势明显", "获胜", "输赢")


def _numbers(text: str) -> list[float]:
    """提取回答中的数字，供证据一致性检查使用。"""
    return [float(v) for v in re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", text)]


def review_answer(question: str, draft_answer: str, evidence: list[dict[str, Any]], limitations: list[str]) -> dict[str, Any]:
    """检查初稿并返回修订文本；不保存或生成模型推断。"""
    evidence_numbers = []
    for item in evidence:
        try:
            evidence_numbers.append(float(item.get("value")))
        except (TypeError, ValueError):
            pass
        try:
            evidence_numbers.append(float(item.get("reliability")))
        except (TypeError, ValueError):
            pass
        evidence_numbers.extend(_numbers(str(item.get("value", ""))))
        evidence_numbers.extend(_numbers(str(item.get("description", ""))))
    rally_question = bool(re.search(r"第\s*[一二三四五六七八九十0-9]+\s*回合|rally", question, re.IGNORECASE))
    issues: list[str] = []
    revised: list[str] = []
    def fact_line(line: str) -> str:
        """从含禁用词的句子中保留能在证据中核对的数值事实。"""
        facts = []
        for item in evidence:
            try:
                value = float(item.get("value"))
            except (TypeError, ValueError):
                continue
            if any(abs(value - number) <= max(0.01, abs(value) * 1e-5) for number in _numbers(line)):
                facts.append(f"{value:g} {item.get('unit', '')}".strip())
        return f"可确认数据：{', '.join(dict.fromkeys(facts))}。" if facts else ""
    for line in draft_answer.splitlines():
        action_found = [term for term in ACTION_TERMS if term in line]
        outcome_found = [term for term in OUTCOME_TERMS if term in line]
        if action_found:
            issues.append(f"unsupported_inference: {', '.join(action_found)}")
            revised.append("检测到相关轨迹统计，但当前数据无法证明其对应具体击球动作。")
            if fact := fact_line(line):
                revised.append(fact)
            continue
        if outcome_found:
            issues.append(f"unsupported_outcome: {', '.join(outcome_found)}")
            revised.append("当前数据没有比分或人工标注，无法判断比赛结果。")
            continue
        if rally_question and any(term in line for term in ("整场比赛", "全场平均", "比赛整体")):
            issues.append("scope_mismatch: 回合问题引用了比赛整体范围")
            revised.append("该指标属于比赛整体范围，不代表指定回合表现。")
            continue
        revised.append(line)
    revised_text = "\n".join(revised)
    for number in _numbers(revised_text):
        if not any(abs(number - candidate) <= max(0.01, abs(candidate) * 1e-5) for candidate in evidence_numbers):
            issues.append(f"evidence_mismatch: 回答数字 {number:g} 不在证据值中")
            break
    if issues and "当前轨迹数据无法证明该结论。" not in revised_text and any("evidence_mismatch" in issue for issue in issues):
        revised_text += "\n\n当前轨迹数据无法证明该结论。"
    if not evidence and question:
        issues.append("no_evidence: 没有可供核对的证据")
    # 通过表示初稿无需规则修订；有问题时返回修订后的事实性文本。
    return {"pass": not issues, "issues": list(dict.fromkeys(issues)), "revised_answer": revised_text}

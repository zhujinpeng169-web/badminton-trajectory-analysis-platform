"""对 Qwen 最终文本做基于规则的安全检查。"""

from __future__ import annotations

from typing import Any


FORBIDDEN_TERMS = (
    "杀球", "吊球", "网前球", "反手", "正手", "技术能力", "战术优势", "获胜", "输赢",
)
SAFETY_NOTE = "当前轨迹数据无法证明该结论。"


def validate_report(report: str) -> dict[str, Any]:
    """保留模型文本，在出现未经证实结论的段落后追加限制说明。"""
    if not isinstance(report, str):
        raise TypeError("report 必须是字符串")
    safe_lines: list[str] = []
    warnings: list[str] = []
    for line in report.splitlines():
        safe_lines.append(line)
        found = [term for term in FORBIDDEN_TERMS if term in line]
        if found and SAFETY_NOTE not in line:
            warnings.append(f"检测到未经证实术语: {', '.join(found)}")
            safe_lines.append(f"> {SAFETY_NOTE}")
    return {"safe_report": "\n".join(safe_lines), "warnings": list(dict.fromkeys(warnings))}

"""用 RAG 分块补全全文解析漏掉的题目。"""
from __future__ import annotations

import json
import re
from pathlib import Path

from src.quiz_parser import Question, parse_text

EXPL = re.compile(r"Explanation:\s*", re.I)
Q_NUM = re.compile(r"(?:^|\n)(\d{1,3})\.\s+")


def _merge_chunks(chunks: list[dict]) -> str:
    parts = [c["text"] for c in chunks]
    return "\n".join(parts)


def extract_from_chunks(chunks_path: Path, source_name: str) -> list[Question]:
    if not chunks_path.exists():
        return []
    chunks: list[dict] = json.loads(chunks_path.read_text(encoding="utf-8"))
    # 只处理目标 PDF 的分块
    related = [c for c in chunks if source_name in c.get("source", c.get("meta", {}).get("path", ""))]
    if not related:
        related = chunks

    expl_indices = [i for i, c in enumerate(related) if EXPL.search(c["text"])]
    found: dict[int, Question] = {}

    for idx in expl_indices:
        # 向前取 2 块、向后取 1 块，拼成完整题目+解析
        start = max(0, idx - 2)
        end = min(len(related), idx + 2)
        blob = _merge_chunks(related[start:end])
        for q in parse_text(blob, source=source_name):
            if q.number not in found or len(q.options) > len(found[q.number].options):
                found[q.number] = q

    return sorted(found.values(), key=lambda x: x.number)


def _question_quality(q: Question) -> int:
    """分数越高表示解析质量越好。"""
    from src.quiz_parser import _normalize

    score = 0
    opt_norm = {_normalize(o) for o in q.options}
    for a in q.answer:
        if _normalize(a) in opt_norm:
            score += 20
        elif any(_normalize(a) in _normalize(o) for o in q.options):
            score += 10
        if len(a) < 25:
            score -= 8
    if any(re.search(r"^\d{1,2}/\d{2}$", o) for o in q.options):
        score -= 30
    if len(q.options) != len({_normalize(o) for o in q.options}):
        score -= 10
    score -= max(0, len(q.options) - 8)
    return score


def merge_question_lists(primary: list[Question], extra: list[Question]) -> list[Question]:
    """仅补全缺失题号；绝不覆盖已有 PDF 红色标注答案。"""
    by_num = {q.number: q for q in primary}
    for q in extra:
        if q.number not in by_num:
            by_num[q.number] = q
        elif by_num[q.number].answer_from_red:
            continue
        elif q.answer_from_red:
            by_num[q.number] = q
        elif _question_quality(q) > _question_quality(by_num[q.number]):
            by_num[q.number] = q
    return sorted(by_num.values(), key=lambda x: x.number)

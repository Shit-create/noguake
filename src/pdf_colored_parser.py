"""从 CCNA 答案 PDF 按红色标注提取正确答案（itexamanswers 全题库通用）。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from src.quiz_parser import (
    CHOOSE_LINE,
    CHOOSE_N,
    NOISE_LINE,
    Question,
    _choose_count,
    _infer_answers,
    _normalize,
)

Q_HEAD = re.compile(r"^(\d{1,3})\.\s+(.*)$")
PAGE_JUNK = re.compile(
    r"^\d{1,2}/\d{2}$|itexamanswers|^\d{4}/\d{1,2}/\d{1,2}|"
    r"Final Exam Answers|CCNA \d v7\.0|Enterprise Networking",
    re.I,
)


def _clean_line(text: str) -> str:
    return re.sub(r"[\uf000-\uf8ff]", "", text).strip()


def _is_red_color(color: int) -> bool:
    r = (color >> 16) & 0xFF
    g = (color >> 8) & 0xFF
    b = color & 0xFF
    return r >= 200 and g < 80 and b < 80


def _extract_colored_lines(path: Path) -> list[tuple[str, bool]]:
    import fitz

    lines: list[tuple[str, bool]] = []
    with fitz.open(str(path)) as doc:
        for page in doc:
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block["lines"]:
                    parts: list[str] = []
                    red = False
                    for span in line["spans"]:
                        parts.append(span["text"])
                        if _is_red_color(span["color"]):
                            red = True
                    txt = _clean_line("".join(parts))
                    if txt and not PAGE_JUNK.search(txt):
                        lines.append((txt, red))
    return lines


def _should_merge_into_prev(prev: str, text: str) -> bool:
    if Q_HEAD.match(text):
        return False
    # 两个完整选项（均以 the/a/an/to/A virus 开头）不合并
    if re.match(r"^(the|a|an|to |it |all |A virus)", text, re.I) and re.match(
        r"^(the|a|an|to |it |all |A virus)", prev, re.I
    ):
        if len(prev) > 25 and len(text) > 15:
            return False
    if re.match(r"^(and|or|of|in|for|with|that|which|from|payload)\b", text, re.I):
        return True
    if prev.rstrip().endswith(","):
        return True
    if len(text.split()) <= 2 and len(prev.split()) >= 8:
        return True
    return False


def _merge_option_lines(rows: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    merged: list[tuple[str, bool]] = []
    for text, red in rows:
        if PAGE_JUNK.search(text) or NOISE_LINE.search(text):
            continue
        if not merged:
            merged.append((text, red))
            continue
        prev, prev_red = merged[-1]
        if _should_merge_into_prev(prev, text):
            merged[-1] = (prev + " " + text, prev_red or red)
        else:
            merged.append((text, red))
    return merged


def _dedupe_options(rows: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    seen: set[str] = set()
    out: list[tuple[str, bool]] = []
    for text, red in rows:
        key = _normalize(text)
        if key in seen or len(key) < 2:
            continue
        seen.add(key)
        out.append((text, red))
    return out


def _parse_block(num: int, block: list[tuple[str, bool]], source: str) -> Question | None:
    stem_parts: list[str] = []
    option_rows: list[tuple[str, bool]] = []
    explanation = ""
    in_expl = False
    stem_closed = False

    for idx, (text, red) in enumerate(block):
        if idx == 0:
            m = Q_HEAD.match(text)
            if m:
                stem_parts.append(m.group(2))
                head = m.group(2)
                if "?" in head or CHOOSE_LINE.match(head) or CHOOSE_N.search(head):
                    stem_closed = True
            continue
        if re.match(r"^Explanation:\s*", text, re.I):
            in_expl = True
            stem_closed = True
            explanation = re.sub(r"^Explanation:\s*", "", text, flags=re.I)
            continue
        if in_expl:
            if not re.match(r"^Topic\s", text, re.I):
                explanation += " " + text
            continue
        if PAGE_JUNK.search(text) or NOISE_LINE.search(text):
            continue
        if not stem_closed:
            stem_parts.append(text)
            if "?" in text or CHOOSE_LINE.match(text):
                stem_closed = True
            continue
        option_rows.append((text, red))

    stem = " ".join(stem_parts).strip()
    if stem and "?" not in stem and not re.search(r"\(choose", stem, re.I):
        stem = stem + "?"

    merged = _dedupe_options(_merge_option_lines(option_rows))
    options = [t for t, _ in merged]
    red_answers = [t for t, r in merged if r]

    if not stem or len(options) < 2:
        return None

    if red_answers:
        answers = red_answers
        from_red = True
    elif explanation.strip():
        answers = _infer_answers(options, explanation, stem)
        from_red = False
    else:
        return None
    if not answers:
        return None

    qtype: Literal["single", "multi"] = (
        "multi" if _choose_count(stem) > 1 or len(answers) > 1 else "single"
    )
    return Question(
        number=num,
        stem=stem,
        options=options,
        answer=answers,
        qtype=qtype,
        source=source,
        answer_from_red=from_red,
    )


def parse_colored_pdf(path: Path, *, max_number: int | None = None) -> list[Question]:
    all_lines = _extract_colored_lines(path)
    by_num: dict[int, Question] = {}
    i = 0

    while i < len(all_lines):
        if not Q_HEAD.match(all_lines[i][0]):
            i += 1
            continue
        num = int(Q_HEAD.match(all_lines[i][0]).group(1))
        if max_number and num > max_number:
            i += 1
            continue

        block = [all_lines[i]]
        i += 1
        found_expl = False
        while i < len(all_lines):
            text, _ = all_lines[i]
            if Q_HEAD.match(text):
                if found_expl:
                    break
                i += 1
                continue
            if re.match(r"^Explanation:\s*", text, re.I):
                found_expl = True
            block.append(all_lines[i])
            i += 1
            if found_expl and i < len(all_lines) and Q_HEAD.match(all_lines[i][0]):
                break

        if not found_expl:
            continue
        q = _parse_block(num, block, path.name)
        if not q:
            continue
        old = by_num.get(num)
        if not old or (q.answer_from_red and not old.answer_from_red):
            by_num[num] = q
        elif q.answer_from_red == old.answer_from_red and len(q.options) > len(old.options):
            by_num[num] = q

    if max_number:
        for num in range(1, max_number + 1):
            if num in by_num and by_num[num].answer_from_red:
                continue
            for i, (text, _) in enumerate(all_lines):
                m = Q_HEAD.match(text)
                if not m or int(m.group(1)) != num:
                    continue
                block = [all_lines[i]]
                j = i + 1
                found_expl = False
                while j < len(all_lines):
                    t2, _ = all_lines[j]
                    if Q_HEAD.match(t2) and found_expl:
                        break
                    if Q_HEAD.match(t2) and not found_expl:
                        j += 1
                        continue
                    if re.match(r"^Explanation:\s*", t2, re.I):
                        found_expl = True
                    block.append(all_lines[j])
                    j += 1
                    if found_expl and j < len(all_lines) and Q_HEAD.match(all_lines[j][0]):
                        break
                if found_expl:
                    q = _parse_block(num, block, path.name)
                    if q:
                        by_num[num] = q
                break

    return sorted(by_num.values(), key=lambda x: x.number)

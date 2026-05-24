"""从 data/ 下的题库 PDF/文本解析选择题（CCNA 答案页等常见格式）。"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from src.document_loader import collect_documents

Q_START = re.compile(r"\n(\d{1,3})\.\s+")
CHOOSE_N = re.compile(r"choose\s+(two|three|four|\d+)", re.I)
CHOOSE_LINE = re.compile(r"^\(choose\s+", re.I)
NOISE_LINE = re.compile(
    r"(Related Posts|Recent Comments|Packet Tracer|Check Your Understanding|"
    r"Module Quiz|on CCNA|on SRWE|itexamanswers|^\d{4}/\d{1,2}/\d{1,2})",
    re.I,
)


@dataclass
class Question:
    number: int
    stem: str
    options: list[str]
    answer: list[str]
    qtype: Literal["single", "multi"]
    source: str
    answer_from_red: bool = False  # True=PDF 红色标注，False=Explanation 推断

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def search_text(self) -> str:
        """用于向量检索的文本。"""
        return _normalize(f"{self.stem} {' '.join(self.options)}")


def _clean_text(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"^\d{4}/\d{1,2}/\d{1,2}[^\n]*\n", "", text, flags=re.M)
    return text


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def _choose_count(stem: str) -> int:
    m = CHOOSE_N.search(stem)
    if not m:
        return 1
    word = m.group(1).lower()
    return {"two": 2, "three": 3, "four": 4}.get(word, int(word) if word.isdigit() else 1)


def _match_score(option: str, explanation: str) -> float:
    opt = _normalize(option)
    expl = _normalize(explanation)
    if len(opt) < 4:
        return 0.0
    if opt in expl:
        return len(opt) + 100.0
    core = re.sub(r"^(the|a|an)\s+", "", opt)
    if len(core) > 8 and core in expl:
        return len(core) + 80.0
    words = [w for w in core.split() if len(w) > 4][:6]
    hit = sum(1 for w in words if w in expl)
    if hit >= max(2, len(words) * 2 // 3):
        return hit * 20.0
    return 0.0


def _is_dismissed(option: str, explanation: str) -> bool:
    expl = _normalize(explanation)
    core = re.sub(r"^(the|a|an)\s+", "", _normalize(option))
    words = [w for w in core.split() if len(w) > 3]
    for i in range(max(1, len(words) - 2)):
        key = " ".join(words[i : i + 3])
        if len(key) < 12:
            continue
        idx = expl.find(key)
        if idx < 0:
            continue
        window = expl[idx : idx + 130]
        if re.search(r"will not|would not|not provide|incorrect|instead", window):
            return True
    return False


def _infer_answers(options: list[str], explanation: str, stem: str) -> list[str]:
    need = _choose_count(stem)
    options = [o for o in options if not CHOOSE_LINE.match(o.strip())]
    if not options:
        return []

    scored = [(o, _match_score(o, explanation)) for o in options]
    scored.sort(key=lambda x: x[1], reverse=True)

    if need > 1:
        picked = [o for o, s in scored if s >= 20.0 and not _is_dismissed(o, explanation)]
        if len(picked) >= need:
            return picked[:need]
        return [o for o, _ in scored[:need]]

    affirm = [o for o, s in scored if s >= 50.0 and not _is_dismissed(o, explanation)]
    if affirm and affirm[0] == scored[0][0]:
        return [affirm[0]]

    candidates = [o for o, s in scored if not _is_dismissed(o, explanation)]
    if not candidates:
        candidates = [o for o, _ in scored]
    by_low = sorted(
        [(o, _match_score(o, explanation)) for o in candidates],
        key=lambda x: x[1],
    )
    return [by_low[0][0]]


OPTION_START = re.compile(
    r"^(the|a|an|it |all |two |three |traffic |one |to |inbound|outbound|leased|"
    r"ISDN|DSL|cable|dialup|hello|borderless|converged|managed|switched|"
    r"Ethernet|digital|municipal|VPN|wireless|fiber|satellite|CPE|DCE|DTE|POP|"
    r"POST|GET|PUT|PATCH|DELETE|permitted|denied|router[\s(]|network\s|\d+$)",
    re.I,
)


def _is_option_continuation(line: str) -> bool:
    """上一行选项的折行续写（非新选项）。"""
    if OPTION_START.match(line):
        return False
    if len(line.split()) <= 4:
        return False
    if re.match(r"^[a-z]", line):
        return True
    return bool(re.match(r"^(to|and|or|of|in|for|with|that|which|from)\s", line, re.I))


def _split_stem_options(block: str) -> tuple[str, list[str]]:
    block = block.strip()
    opt_body = ""
    stem = ""

    m = re.search(r"^(.*?)\?(?:\s*\([^)]+\))?\s*\n(.*)$", block, re.S)
    if m:
        stem = m.group(1).strip() + "?"
        opt_body = m.group(2)
        m2 = re.search(r"\?\s*(\(choose[^)]+\))", block, re.I)
        if m2 and m2.group(1).lower() not in stem.lower():
            stem = stem + " " + m2.group(1)
    else:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        start = len(lines)
        for i, ln in enumerate(lines):
            if NOISE_LINE.search(ln):
                start = i
                break
            if OPTION_START.match(ln) or re.match(r"^\d+$", ln):
                start = i
                break
        if start >= len(lines):
            return "", []
        stem = " ".join(lines[:start])
        opt_body = "\n".join(lines[start:])

    options: list[str] = []
    for ln in opt_body.splitlines():
        ln = ln.strip()
        if not ln or NOISE_LINE.search(ln):
            break
        if CHOOSE_LINE.match(ln):
            stem = stem + " " + ln
            continue
        # 短选项（ISDN / cable）或新句子开头 -> 新选项；小写长句 -> 续行
        if not options or not _is_option_continuation(ln):
            options.append(ln)
        else:
            options[-1] = options[-1] + " " + ln

    options = [o for o in options if len(o) >= 2]
    if len(options) == 1 and re.search(r"permitted or denied", stem, re.I):
        options = ["permitted", "denied"]
    return stem, options


def _try_parse_block(num: int, body: str, explanation: str, source: str) -> Question | None:
    stem, options = _split_stem_options(body)
    if not stem or len(options) < 1 or len(explanation) < 15:
        return None
    if len(options) < 2 and not re.search(r"permitted or denied", stem, re.I):
        return None
    answers = _infer_answers(options, explanation, stem)
    if not answers:
        return None
    need = _choose_count(stem)
    qtype: Literal["single", "multi"] = "multi" if need > 1 else "single"
    return Question(
        number=num,
        stem=stem,
        options=options,
        answer=answers,
        qtype=qtype,
        source=source,
    )


def parse_text(text: str, source: str = "", *, max_number: int | None = None) -> list[Question]:
    text = _clean_text(text)
    markers = list(Q_START.finditer(text))
    by_num: dict[int, Question] = {}

    for i, m in enumerate(markers):
        num = int(m.group(1))
        if max_number and num > max_number:
            continue
        start = m.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        chunk = text[start:end]

        expl_m = re.search(r"\nExplanation:\s*(.*)", chunk, re.S | re.I)
        if not expl_m:
            continue

        body = chunk[: expl_m.start()]
        explanation = expl_m.group(1).strip()
        cut = Q_START.search(explanation)
        if cut:
            explanation = explanation[: cut.start()]

        q = _try_parse_block(num, body, explanation, source)
        if q and (num not in by_num or len(q.options) > len(by_num[num].options)):
            by_num[num] = q

    # 按题号 1..max 宽窗口补全（跳过网页垃圾区）
    if max_number:
        for num in range(1, max_number + 1):
            if num in by_num:
                continue
            m = re.search(rf"(?<=\n){num}\.\s+", text)
            if not m:
                continue
            chunk = text[m.end() : m.end() + 12000]
            expl_m = re.search(r"\nExplanation:\s*(.*)", chunk, re.S | re.I)
            if not expl_m:
                continue
            body = chunk[: expl_m.start()]
            explanation = expl_m.group(1).strip()[:2500]
            q = _try_parse_block(num, body, explanation, source)
            if q and (num not in by_num or len(q.options) > len(by_num[num].options)):
                by_num[num] = q

    return sorted(by_num.values(), key=lambda x: x.number)


def parse_question_bank(
    data_dir: Path,
    *,
    max_number: int | None = None,
    source_filter: str | None = None,
    use_pdf_colors: bool = True,
) -> list[Question]:
    all_q: list[Question] = []
    for path, text in collect_documents(data_dir):
        if source_filter and source_filter not in path.name:
            continue
        qs: list[Question] = []
        by_num: dict[int, Question] = {}
        if use_pdf_colors and path.suffix.lower() == ".pdf":
            try:
                from src.pdf_colored_parser import parse_colored_pdf

                for q in parse_colored_pdf(path, max_number=max_number):
                    by_num[q.number] = q
            except Exception as e:
                import logging

                logging.warning("红色标注解析失败 [%s]: %s", path.name, e)
        for q in parse_text(text, source=path.name, max_number=max_number):
            if q.number not in by_num:
                q.answer_from_red = False
                by_num[q.number] = q
            elif not by_num[q.number].answer_from_red and not q.answer_from_red:
                if len(q.options) > len(by_num[q.number].options):
                    by_num[q.number] = q
        if max_number:
            by_num = {n: q for n, q in by_num.items() if n <= max_number}
        all_q.extend(by_num.values())
    return sorted(all_q, key=lambda x: (x.source, x.number))


def save_questions(questions: list[Question], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps([q.to_dict() for q in questions], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_questions(path: Path) -> list[Question]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[Question] = []
    for item in data:
        item.setdefault("answer_from_red", False)
        out.append(Question(**item))
    return out

#!/usr/bin/env python3
"""解析 data/ 题库：全卷按 PDF 红色标注识别答案，生成 questions.json。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.panel import Panel

from src.config import load_config
from src.document_loader import collect_documents
from src.question_matcher import QuestionMatcher
from src.quiz_parser import parse_question_bank, save_questions
from src.quiz_rag_extract import extract_from_chunks, merge_question_lists

console = Console()


def main() -> None:
    cfg = load_config()
    data_dir = Path(cfg["paths"]["data_dir"])
    index_dir = Path(cfg["paths"]["index_dir"])
    quiz_cfg = cfg.get("quiz", {})
    source_filter = quiz_cfg.get("source_filter")
    max_num = quiz_cfg.get("max_question_number")

    console.print(Panel.fit(
        f"[bold]解析题库（PDF 红色标注 = 正确答案）[/bold]\n数据目录：{data_dir}",
        border_style="cyan",
    ))

    questions = parse_question_bank(
        data_dir,
        max_number=max_num,
        source_filter=source_filter,
        use_pdf_colors=True,
    )
    red_n = sum(1 for q in questions if q.answer_from_red)
    console.print(
        f"PDF 红色标注解析：[green]{red_n}[/green] 道 | "
        f"其余推断补全：[yellow]{len(questions) - red_n}[/yellow] 道"
    )

    chunks_path = index_dir / "chunks.json"
    if chunks_path.exists() and source_filter:
        rag_qs = extract_from_chunks(chunks_path, source_filter)
        before = len(questions)
        questions = merge_question_lists(questions, rag_qs)
        added = len(questions) - before
        if added:
            console.print(f"RAG 仅补全缺失题号：[green]+{added}[/green] 道")

    if max_num:
        questions = [q for q in questions if q.number <= max_num]

    if not questions:
        console.print("[red]未能解析出题目，请检查 data/ 内 PDF[/red]")
        return

    nums = {q.number for q in questions}
    if max_num:
        missing = sorted(set(range(1, max_num + 1)) - nums)
        if missing:
            console.print(f"[yellow]仍缺少题号：{len(missing)} 个[/yellow] {missing[:12]}…")

    out = index_dir / "questions.json"
    save_questions(questions, out)
    red_n = sum(1 for q in questions if q.answer_from_red)
    console.print(
        f"[bold green]共 {len(questions)} 道题[/bold green] "
        f"（[green]{red_n}[/green] 道来自红色标注）→ {out}"
    )

    matcher = QuestionMatcher(cfg)
    matcher.questions = questions
    console.print("正在构建题目向量索引…")
    matcher.build_index()
    console.print(f"[bold green]完成！[/bold green] 双击「开始提问.bat」输入题目查答案。")


if __name__ == "__main__":
    main()

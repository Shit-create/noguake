#!/usr/bin/env python3
"""输入题目内容，从题库向量检索匹配原题并返回正确答案。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import load_config
from src.question_matcher import QuestionMatcher
from src.quiz_parser import parse_question_bank, save_questions
from src.quiz_rag_extract import extract_from_chunks, merge_question_lists
from src.rag_engine import RAGEngine, build_context

console = Console()


def ensure_bank(cfg: dict) -> QuestionMatcher:
    index_dir = Path(cfg["paths"]["index_dir"])
    cache = index_dir / "questions.json"
    quiz_cfg = cfg.get("quiz", {})
    matcher = QuestionMatcher(cfg)

    if matcher.load():
        return matcher

    console.print("[yellow]题库未就绪，正在解析 data/ …[/yellow]")
    data_dir = Path(cfg["paths"]["data_dir"])
    questions = parse_question_bank(
        data_dir,
        max_number=quiz_cfg.get("max_question_number"),
        source_filter=quiz_cfg.get("source_filter"),
    )
    chunks_path = index_dir / "chunks.json"
    if chunks_path.exists() and quiz_cfg.get("source_filter"):
        questions = merge_question_lists(
            questions,
            extract_from_chunks(chunks_path, quiz_cfg["source_filter"]),
        )
    if questions:
        save_questions(questions, cache)
        matcher.questions = questions
        matcher.build_index()
    return matcher


def _rag_fallback(cfg: dict, query: str) -> str | None:
    """向量库片段兜底：从检索到的正文里整理答案。"""
    index_path = Path(cfg["paths"]["index_dir"]) / "index.faiss"
    if not index_path.exists():
        return None
    try:
        engine = RAGEngine(cfg)
        hits = engine.retrieve(query)
        if not hits:
            return None
        ctx = build_context(hits, max_chars=4000)
        return (
            "[dim]未精确匹配到原题，以下为知识库检索片段（含答案解析）：[/dim]\n\n"
            + ctx
        )
    except Exception:
        return None


def main() -> None:
    cfg = load_config()
    course = cfg["course"]
    matcher = ensure_bank(cfg)

    if not matcher.questions:
        console.print(
            "[red]题库为空！请先双击「解析题库.bat」或「构建知识库.bat」+「解析题库.bat」[/red]"
        )
        input("\n按回车退出…")
        return

    console.print(Panel.fit(
        f"[bold cyan]{course['university']} · {course['major']}[/bold cyan]\n"
        f"《{course['course_name']}》查答案\n"
        f"题库共 [green]{len(matcher.questions)}[/green] 道 | "
        f"粘贴/输入题目文字，回车查正确答案 | 输入 q 退出",
        border_style="green",
    ))

    while True:
        try:
            query = console.input("\n[bold yellow]题目内容[/bold yellow] > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not query:
            continue
        if query.lower() in ("q", "quit", "exit", "退出"):
            break

        hits = matcher.lookup(query, top_k=3)
        if hits:
            score, best = hits[0]
            console.print(
                f"\n[dim]匹配题号 {best.number} | 相似度 {score:.2f} | 来源 {best.source}[/dim]\n"
            )
            console.print(Panel(
                QuestionMatcher.format_answer(best),
                title="正确答案",
                border_style="green",
            ))
            if len(hits) > 1:
                table = Table(title="其他可能匹配", show_header=True)
                table.add_column("#", width=3)
                table.add_column("相似度", width=8)
                table.add_column("题号", width=6)
                table.add_column("题干", overflow="ellipsis")
                for i, (s, q) in enumerate(hits[1:], 2):
                    table.add_row(str(i), f"{s:.2f}", str(q.number), q.stem[:60] + "…")
                console.print(table)
        else:
            console.print("[yellow]题库中未找到足够相似的题目，尝试 RAG 检索…[/yellow]")
            fallback = _rag_fallback(cfg, query)
            if fallback:
                console.print(Panel(fallback, title="检索片段", border_style="blue"))
            else:
                console.print(
                    "[red]未找到匹配。请：[/red]\n"
                    "  1. 多输入一些题干关键词\n"
                    "  2. 运行「构建知识库.bat」后再试\n"
                    "  3. 检查 config.yaml 中 quiz.source_filter"
                )

    console.print("\n再见！")


if __name__ == "__main__":
    main()

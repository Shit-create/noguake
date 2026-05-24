"""题库构建与查答案核心服务（CLI / Web 共用）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.library_manager import LibraryManager
from src.question_matcher import QuestionMatcher
from src.quiz_parser import Question, _normalize, parse_question_bank, save_questions
from src.quiz_rag_extract import extract_from_chunks, merge_question_lists
from src.rag_engine import RAGEngine, build_context

_matcher_cache: dict[str, QuestionMatcher] = {}
_MAX_CACHE_SIZE = 3


def build_library(
    lib_id: str,
    *,
    build_rag: bool = True,
    manager: LibraryManager | None = None,
) -> dict[str, Any]:
    mgr = manager or LibraryManager()
    cfg = mgr.load_config(lib_id)
    data_dir = Path(cfg["paths"]["data_dir"])
    index_dir = Path(cfg["paths"]["index_dir"])

    if not any(data_dir.iterdir()) if data_dir.exists() else True:
        raise ValueError("请先上传题库文件")

    if build_rag:
        _build_rag_chunks(cfg, data_dir, index_dir)

    questions = parse_question_bank(
        data_dir,
        max_number=cfg.get("quiz", {}).get("max_question_number"),
        source_filter=cfg.get("quiz", {}).get("source_filter") or None,
        use_pdf_colors=cfg.get("quiz", {}).get("use_pdf_colors", True),
    )

    chunks_path = index_dir / "chunks.json"
    if chunks_path.exists():
        rag_qs = []
        for f in data_dir.iterdir():
            if f.is_file():
                rag_qs.extend(extract_from_chunks(chunks_path, f.name))
        if rag_qs:
            questions = merge_question_lists(questions, rag_qs)

    if not questions:
        raise ValueError("未能从上传的文件解析出题目，请确认 PDF 含选项与 Explanation")

    save_questions(questions, index_dir / "questions.json")
    matcher = QuestionMatcher(cfg)
    matcher.questions = questions
    matcher.build_index()
    while len(_matcher_cache) >= _MAX_CACHE_SIZE:
        _matcher_cache.pop(next(iter(_matcher_cache)))
    _matcher_cache[lib_id] = matcher

    red_n = sum(1 for q in questions if q.answer_from_red)
    meta = mgr.update_build_stats(
        lib_id,
        question_count=len(questions),
        red_count=red_n,
        status="ready",
    )
    return {
        "question_count": len(questions),
        "red_count": red_n,
        "inferred_count": len(questions) - red_n,
        "library": meta,
    }


def _build_rag_chunks(cfg: dict, data_dir: Path, index_dir: Path) -> None:
    from src.chunker import build_chunks
    from src.document_loader import collect_documents
    from src.embeddings import get_embedder
    from src.vector_store import FaissStore

    docs = collect_documents(data_dir)
    if not docs:
        return
    chunks = build_chunks(
        docs,
        cfg["chunking"]["chunk_size"],
        cfg["chunking"]["chunk_overlap"],
    )
    embedder = get_embedder(
        cfg["embedding"]["model"],
        device=cfg["embedding"].get("device", "cpu"),
    )
    vectors = embedder.encode(
        [c.text for c in chunks],
        batch_size=cfg["embedding"].get("batch_size", 32),
    )
    store = FaissStore(index_dir)
    store.build(vectors, chunks)


def get_matcher(lib_id: str, manager: LibraryManager | None = None) -> QuestionMatcher:
    if lib_id in _matcher_cache:
        m = _matcher_cache[lib_id]
        if m.load():
            return m
    mgr = manager or LibraryManager()
    cfg = mgr.load_config(lib_id)
    matcher = QuestionMatcher(cfg)
    if not matcher.load():
        raise ValueError("题库尚未构建，请先在「我的题库」中点击构建索引")
    while len(_matcher_cache) >= _MAX_CACHE_SIZE:
        _matcher_cache.pop(next(iter(_matcher_cache)))
    _matcher_cache[lib_id] = matcher
    return matcher


def search_question(
    lib_id: str,
    query: str,
    *,
    top_k: int = 3,
    manager: LibraryManager | None = None,
) -> dict[str, Any]:
    query = query.strip()
    if not query:
        raise ValueError("请输入题目内容")

    mgr = manager or LibraryManager()
    cfg = mgr.load_config(lib_id)
    matcher = get_matcher(lib_id, mgr)

    hits = matcher.lookup(query, top_k=top_k)
    if hits:
        score, best = hits[0]
        alts = [
            {
                "score": round(s, 3),
                "number": q.number,
                "stem": q.stem[:120],
            }
            for s, q in hits[1:]
        ]
        return {
            "found": True,
            "score": round(score, 3),
            "question": _question_to_dict(best),
            "formatted": QuestionMatcher.format_answer(best),
            "alternatives": alts,
        }

    fallback = _rag_fallback(cfg, query)
    if fallback:
        return {"found": False, "fallback": fallback, "question": None}

    return {
        "found": False,
        "message": "未找到匹配题目，请多输入题干关键词或重新构建题库",
        "question": None,
    }


def _question_to_dict(q: Question) -> dict[str, Any]:
    labels = [chr(ord("A") + i) for i in range(len(q.options))]
    ans_norm = {_normalize(a) for a in q.answer}
    return {
        "number": q.number,
        "stem": q.stem,
        "qtype": q.qtype,
        "options": [
            {
                "label": labels[i],
                "text": opt,
                "correct": _normalize(opt) in ans_norm,
            }
            for i, opt in enumerate(q.options)
        ],
        "answer": q.answer,
        "answer_from_red": q.answer_from_red,
        "source": q.source,
    }


def _rag_fallback(cfg: dict, query: str) -> str | None:
    index_path = Path(cfg["paths"]["index_dir"]) / "index.faiss"
    if not index_path.exists():
        return None
    try:
        engine = RAGEngine(cfg)
        hits = engine.retrieve(query)
        if not hits:
            return None
        return build_context(hits, max_chars=4000)
    except Exception:
        return None

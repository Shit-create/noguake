"""题库向量检索：用户输入题目文本，匹配最接近的原题并返回答案。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from src.embeddings import get_embedder
from src.quiz_parser import Question, _normalize, load_questions
from src.vector_store import _faiss_read, _faiss_write


class QuestionMatcher:
    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.index_dir = Path(cfg["paths"]["index_dir"])
        self.questions_path = self.index_dir / "questions.json"
        self.index_path = self.index_dir / "questions.faiss"
        self.meta_path = self.index_dir / "questions_meta.json"

        self.embedder = get_embedder(
            cfg["embedding"]["model"],
            device=cfg["embedding"].get("device", "cpu"),
        )
        self.questions: list[Question] = []
        self.index: faiss.Index | None = None

    def load(self) -> bool:
        if not self.questions_path.exists():
            return False
        self.questions = load_questions(self.questions_path)
        if not self.questions or not self.index_path.exists():
            return False
        self.index = _faiss_read(self.index_path)
        if hasattr(self.index, "nprobe"):
            self.index.nprobe = min(4, self.index.nlist)
        return True

    def build_index(self, questions: list[Question] | None = None) -> None:
        if questions is not None:
            self.questions = questions
        if not self.questions:
            return

        texts = [q.search_text for q in self.questions]
        vecs = self.embedder.encode(
            texts, batch_size=self.cfg["embedding"].get("batch_size", 32)
        )
        dim = vecs.shape[1]
        nlist = max(1, int(len(texts) ** 0.5))
        if len(texts) >= 50 and nlist > 1:
            quantizer = faiss.IndexFlatIP(dim)
            index = faiss.IndexIVFFlat(
                quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT
            )
            index.train(vecs)
            index.nprobe = min(4, nlist)
        else:
            index = faiss.IndexFlatIP(dim)
        index.add(vecs)
        self.index = index

        self.index_dir.mkdir(parents=True, exist_ok=True)
        _faiss_write(index, self.index_path)
        meta = [{"number": q.number, "source": q.source} for q in self.questions]
        self.meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    def lookup(self, query: str, top_k: int = 3) -> list[tuple[float, Question]]:
        if not self.index or not self.questions:
            return []
        qvec = self.embedder.encode([query])[0].reshape(1, -1).astype(np.float32)
        k = min(top_k, len(self.questions))
        scores, indices = self.index.search(qvec, k)
        results: list[tuple[float, Question]] = []
        threshold = self.cfg.get("quiz", {}).get("match_threshold", 0.45)
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or score < threshold:
                continue
            results.append((float(score), self.questions[idx]))
        return results

    @staticmethod
    def format_answer(q: Question) -> str:
        labels = [chr(ord("A") + i) for i in range(len(q.options))]
        ans_set = {_normalize(a) for a in q.answer}

        src = "PDF红色标注" if getattr(q, "answer_from_red", False) else "解析推断"
        lines = [
            f"【题号】{q.number}",
            f"【题型】{'多选' if q.qtype == 'multi' else '单选'}",
            f"【来源】{src}",
            "",
        ]
        lines.append("【正确答案】")
        for i, opt in enumerate(q.options):
            if _normalize(opt) in ans_set:
                lines.append(f"  ★ [{labels[i]}] {opt}")
        if not any(_normalize(o) in ans_set for o in q.options):
            for a in q.answer:
                lines.append(f"  ★ {a}")
        lines.append("")
        lines.append("【全部选项】")
        for lab, opt in zip(labels, q.options):
            mark = " ★" if _normalize(opt) in ans_set else ""
            lines.append(f"  [{lab}]{mark} {opt}")
        return "\n".join(lines)

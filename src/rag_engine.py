from __future__ import annotations

import time
from typing import Any

import requests

from src.embeddings import get_embedder
from src.vector_store import FaissStore

SYSTEM_PROMPT = """你是{university}{major}《{course_name}》的期末复习助教，授课教师：{professor}。
你只能根据下面「参考资料」回答，不要编造课件或真题里没有的内容。
若资料不足，明确说「当前知识库未收录相关内容」，并建议补充哪些文件。
回答结构：①考点概括 ②历年考法（若有） ③公式/步骤 ④易错点。用中文，简洁有力。"""


def build_context(hits: list[tuple[float, dict]], max_chars: int = 6000) -> str:
    parts = []
    total = 0
    for rank, (score, chunk) in enumerate(hits, 1):
        block = (
            f"--- 片段{rank} | 来源:{chunk['source']} | 相关度:{score:.2f} ---\n"
            f"{chunk['text']}\n"
        )
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts) if parts else "（无匹配片段）"


class RAGEngine:
    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.embedder = get_embedder(
            cfg["embedding"]["model"],
            device=cfg["embedding"].get("device", "cpu"),
        )
        self.store = FaissStore(cfg["paths"]["index_dir"])
        self.store.load()

    def retrieve(self, question: str) -> list[tuple[float, dict]]:
        qvec = self.embedder.encode([question])[0]
        hits = self.store.search(qvec, top_k=self.cfg["retrieval"]["top_k"])
        threshold = self.cfg["retrieval"].get("score_threshold", 0.35)
        return [(s, c) for s, c in hits if s >= threshold]

    def ask(self, question: str) -> dict[str, Any]:
        t0 = time.perf_counter()
        hits = self.retrieve(question)
        retrieve_ms = (time.perf_counter() - t0) * 1000

        course = self.cfg["course"]
        context = build_context(hits)
        system = SYSTEM_PROMPT.format(**course)
        user_msg = f"学生问题：{question}\n\n参考资料：\n{context}"

        t1 = time.perf_counter()
        answer = self._call_ollama(system, user_msg)
        llm_ms = (time.perf_counter() - t1) * 1000

        return {
            "answer": answer,
            "hits": hits,
            "retrieve_ms": round(retrieve_ms, 1),
            "llm_ms": round(llm_ms, 1),
            "total_ms": round(retrieve_ms + llm_ms, 1),
        }

    def _call_ollama(self, system: str, user: str) -> str:
        ollama = self.cfg["ollama"]
        url = f"{ollama['base_url'].rstrip('/')}/api/chat"
        payload = {
            "model": ollama["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": ollama.get("temperature", 0.3),
                "num_predict": ollama.get("num_predict", 1024),
            },
        }
        try:
            r = requests.post(url, json=payload, timeout=120)
            r.raise_for_status()
            return r.json()["message"]["content"]
        except requests.ConnectionError:
            return (
                "无法连接 Ollama。请先安装并运行：ollama serve\n"
                f"然后执行：ollama pull {ollama['model']}"
            )
        except Exception as e:
            return f"模型调用失败: {e}"

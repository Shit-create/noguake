#!/usr/bin/env python3
"""扫描 data/ 目录，构建 FAISS 本地知识库。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.panel import Panel

from src.chunker import build_chunks
from src.config import load_config
from src.document_loader import collect_documents
from src.embeddings import Embedder
from src.vector_store import FaissStore

console = Console()


def main() -> None:
    cfg = load_config()
    data_dir = Path(cfg["paths"]["data_dir"])
    index_dir = Path(cfg["paths"]["index_dir"])

    console.print(Panel.fit(
        f"[bold]构建知识库[/bold]\n"
        f"课程：{cfg['course']['course_name']}\n"
        f"数据目录：{data_dir}",
        border_style="cyan",
    ))

    if not data_dir.exists():
        data_dir.mkdir(parents=True)
        console.print("[yellow]已创建 data/ 目录，请放入 PDF/PPT/Word/TXT 后重新运行。[/yellow]")
        return

    docs = collect_documents(data_dir)
    if not docs:
        console.print("[red]data/ 下没有找到可解析的文件（支持 pdf pptx docx txt md）[/red]")
        return

    console.print(f"共加载 [green]{len(docs)}[/green] 个文件")
    for p, _ in docs:
        console.print(f"  · {p.name}")

    chunks = build_chunks(
        docs,
        cfg["chunking"]["chunk_size"],
        cfg["chunking"]["chunk_overlap"],
    )
    console.print(f"切分为 [green]{len(chunks)}[/green] 个文本块，正在向量化…")

    embedder = Embedder(
        cfg["embedding"]["model"],
        device=cfg["embedding"].get("device", "cpu"),
    )
    texts = [c.text for c in chunks]
    vectors = embedder.encode(texts, batch_size=cfg["embedding"].get("batch_size", 32))

    store = FaissStore(index_dir)
    store.build(vectors, chunks)
    console.print(f"[bold green]完成！[/bold green] 索引已保存到 {index_dir}")


if __name__ == "__main__":
    main()

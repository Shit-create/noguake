from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import faiss
import numpy as np

from src.chunker import Chunk


def _faiss_write(index: faiss.Index, dest: Path) -> None:
    """FAISS C++ IO on Windows cannot open Unicode paths; write via ASCII temp."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest_str = str(dest)
    try:
        faiss.write_index(index, dest_str)
        return
    except RuntimeError:
        if sys.platform != "win32":
            raise
    fd, tmp = tempfile.mkstemp(suffix=".faiss", prefix="campus_rag_")
    os.close(fd)
    try:
        faiss.write_index(index, tmp)
        shutil.copyfile(tmp, dest_str)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _faiss_read(path: Path) -> faiss.Index:
    path_str = str(path)
    try:
        return faiss.read_index(path_str)
    except RuntimeError:
        if sys.platform != "win32":
            raise
    fd, tmp = tempfile.mkstemp(suffix=".faiss", prefix="campus_rag_")
    os.close(fd)
    try:
        shutil.copyfile(path_str, tmp)
        return faiss.read_index(tmp)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


class FaissStore:
    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / "index.faiss"
        self.meta_path = self.index_dir / "chunks.json"
        self.index: faiss.Index | None = None
        self.chunks: list[dict] = []

    def build(self, embeddings: np.ndarray, chunks: list[Chunk]) -> None:
        dim = embeddings.shape[1]
        n = embeddings.shape[0]
        nlist = max(1, int(n ** 0.5))
        if n >= 50 and nlist > 1:
            quantizer = faiss.IndexFlatIP(dim)
            index = faiss.IndexIVFFlat(
                quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT
            )
            index.train(embeddings)
            index.nprobe = min(4, nlist)
        else:
            index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        self.index = index
        self.chunks = [
            {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "source": c.source,
                "meta": c.meta,
            }
            for c in chunks
        ]
        _faiss_write(index, self.index_path)
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, ensure_ascii=False, indent=0)

    def load(self) -> bool:
        if not self.index_path.exists() or not self.meta_path.exists():
            return False
        self.index = _faiss_read(self.index_path)
        if hasattr(self.index, "nprobe"):
            self.index.nprobe = min(4, self.index.nlist)
        with open(self.meta_path, encoding="utf-8") as f:
            self.chunks = json.load(f)
        return True

    def search(
        self, query_vec: np.ndarray, top_k: int = 6
    ) -> list[tuple[float, dict]]:
        if self.index is None or not self.chunks:
            return []
        q = query_vec.reshape(1, -1).astype(np.float32)
        scores, indices = self.index.search(q, min(top_k, len(self.chunks)))
        results: list[tuple[float, dict]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            results.append((float(score), self.chunks[idx]))
        return results

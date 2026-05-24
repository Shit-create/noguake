from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chunk:
    text: str
    source: str
    chunk_id: int
    meta: dict


def split_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            for sep in ("\n\n", "\n", "。", "；", ". ", " "):
                pos = text.rfind(sep, start + chunk_size // 2, end)
                if pos > start:
                    end = pos + len(sep)
                    break
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        start = max(start + 1, end - overlap)
    return chunks


def build_chunks(
    documents: list[tuple[Path, str]],
    chunk_size: int,
    overlap: int,
) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    cid = 0
    for path, text in documents:
        rel = path.name
        parts = split_text(text, chunk_size, overlap)
        for i, part in enumerate(parts):
            all_chunks.append(
                Chunk(
                    text=part,
                    source=rel,
                    chunk_id=cid,
                    meta={"part": i, "path": str(path)},
                )
            )
            cid += 1
    return all_chunks

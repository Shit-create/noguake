from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.paths import app_root, user_data_root

ROOT = app_root()


def load_config(path: Path | None = None, *, library_base: Path | None = None) -> dict[str, Any]:
    cfg_path = path or app_root() / "config.yaml"
    if not cfg_path.exists():
        cfg = _default_config()
    else:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    base = library_base or user_data_root()
    cfg.setdefault("paths", {})
    cfg.setdefault("course", {})
    cfg.setdefault("quiz", {})
    cfg.setdefault("embedding", {"model": "BAAI/bge-small-zh-v1.5", "device": "cpu", "batch_size": 32})
    cfg.setdefault("chunking", {"chunk_size": 500, "chunk_overlap": 80})
    cfg.setdefault("retrieval", {"top_k": 6, "score_threshold": 0.35})
    cfg.setdefault("ollama", {"base_url": "http://127.0.0.1:11434", "model": "qwen2.5:3b"})
    cfg["_root"] = str(app_root())
    cfg["paths"]["data_dir"] = str(base / "data")
    cfg["paths"]["index_dir"] = str(base / "knowledge_base")
    return cfg


def _default_config() -> dict[str, Any]:
    return {
        "course": {"university": "", "major": "", "course_name": "我的题库", "professor": ""},
        "quiz": {
            "source_filter": "",
            "max_question_number": None,
            "match_threshold": 0.45,
            "use_pdf_colors": True,
        },
        "paths": {"data_dir": "data", "index_dir": "knowledge_base"},
        "embedding": {"model": "BAAI/bge-small-zh-v1.5", "device": "cpu", "batch_size": 32},
        "chunking": {"chunk_size": 500, "chunk_overlap": 80},
        "retrieval": {"top_k": 6, "score_threshold": 0.35},
        "ollama": {"base_url": "http://127.0.0.1:11434", "model": "qwen2.5:3b"},
    }

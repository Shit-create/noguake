"""多题库管理：每个用户题库独立目录。"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.paths import app_root, libraries_dir

ROOT = app_root()
LIBRARIES_DIR = libraries_dir()
META_FILE = "library.json"
ALLOWED_EXT = {".pdf", ".txt", ".md", ".docx", ".pptx"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(name: str) -> str:
    """题库显示名称（可截断）。"""
    return re.sub(r'[<>:"/\\|?*]', "_", name.strip())[:80] or "未命名题库"


def _safe_filename(filename: str) -> str:
    """保留扩展名，只清理/截断主文件名。"""
    raw = Path(filename or "upload.pdf").name
    suffix = Path(raw).suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise ValueError(
            f"不支持格式「{suffix or '(无扩展名)'}」，请上传: {', '.join(sorted(ALLOWED_EXT))}"
        )
    stem = re.sub(r'[<>:"/\\|?*]', "_", Path(raw).stem.strip())[:120] or "upload"
    return stem + suffix


class LibraryManager:
    def __init__(self, root: Path | None = None):
        self.root = root or LIBRARIES_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def list_libraries(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not self.root.exists():
            return out
        for path in sorted(self.root.iterdir()):
            if not path.is_dir():
                continue
            meta = self._read_meta(path)
            if meta:
                out.append(meta)
        return sorted(out, key=lambda x: x.get("updated_at", ""), reverse=True)

    def get_library(self, lib_id: str) -> dict[str, Any] | None:
        path = self.root / lib_id
        if not path.is_dir():
            return None
        return self._read_meta(path)

    def create_library(self, name: str, course_name: str = "") -> dict[str, Any]:
        lib_id = str(uuid.uuid4())[:8]
        path = self.root / lib_id
        path.mkdir(parents=True)
        (path / "data").mkdir()
        (path / "knowledge_base").mkdir()

        meta = {
            "id": lib_id,
            "name": _safe_name(name),
            "course_name": course_name or _safe_name(name),
            "created_at": _now(),
            "updated_at": _now(),
            "file_count": 0,
            "question_count": 0,
            "red_count": 0,
            "built_at": None,
            "status": "empty",
        }
        self._write_meta(path, meta)
        self._write_config(path, meta)
        return meta

    def delete_library(self, lib_id: str) -> bool:
        path = self.root / lib_id
        if not path.is_dir():
            return False
        import shutil

        shutil.rmtree(path)
        return True

    def list_files(self, lib_id: str) -> list[dict[str, Any]]:
        data_dir = self.root / lib_id / "data"
        if not data_dir.exists():
            return []
        files = []
        for f in sorted(data_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in ALLOWED_EXT:
                files.append(
                    {
                        "name": f.name,
                        "size": f.stat().st_size,
                        "suffix": f.suffix.lower(),
                    }
                )
        return files

    def save_upload(self, lib_id: str, filename: str, content: bytes) -> str:
        path = self.root / lib_id
        if not path.is_dir():
            raise FileNotFoundError("题库不存在")
        if not content:
            raise ValueError("文件为空，请重新选择")
        safe = _safe_filename(filename)
        dest = path / "data" / safe
        dest.write_bytes(content)
        self._touch_meta(path, file_count=len(list((path / "data").glob("*"))))
        return safe

    def delete_file(self, lib_id: str, filename: str) -> bool:
        path = self.root / lib_id / "data" / _safe_name(filename)
        if path.is_file():
            path.unlink()
            self._touch_meta(self.root / lib_id)
            return True
        return False

    def library_paths(self, lib_id: str) -> tuple[Path, Path, Path]:
        base = self.root / lib_id
        return base, base / "data", base / "knowledge_base"

    def load_config(self, lib_id: str) -> dict[str, Any]:
        base, data_dir, index_dir = self.library_paths(lib_id)
        cfg_path = base / "config.yaml"
        if not cfg_path.exists():
            meta = self._read_meta(base) or {}
            self._write_config(base, meta)
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        cfg["_root"] = str(base)
        cfg["paths"]["data_dir"] = str(data_dir)
        cfg["paths"]["index_dir"] = str(index_dir)
        cfg["library_id"] = lib_id
        return cfg

    def update_build_stats(
        self,
        lib_id: str,
        *,
        question_count: int,
        red_count: int,
        status: str = "ready",
    ) -> dict[str, Any]:
        path = self.root / lib_id
        meta = self._read_meta(path) or {}
        meta["question_count"] = question_count
        meta["red_count"] = red_count
        meta["built_at"] = _now()
        meta["updated_at"] = _now()
        meta["status"] = status
        meta["file_count"] = len(list((path / "data").glob("*")))
        self._write_meta(path, meta)
        return meta

    def _read_meta(self, path: Path) -> dict[str, Any] | None:
        f = path / META_FILE
        if not f.exists():
            return None
        return json.loads(f.read_text(encoding="utf-8"))

    def _write_meta(self, path: Path, meta: dict[str, Any]) -> None:
        (path / META_FILE).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _write_config(self, path: Path, meta: dict[str, Any]) -> None:
        template = ROOT / "config.yaml"
        if template.exists():
            with open(template, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        else:
            cfg = {}
        cfg.setdefault("course", {})
        cfg["course"]["course_name"] = meta.get("course_name", meta.get("name", ""))
        cfg.setdefault("quiz", {})
        cfg["quiz"]["source_filter"] = ""  # 用户题库解析全部文件
        cfg["quiz"]["max_question_number"] = None
        cfg["paths"] = {"data_dir": "data", "index_dir": "knowledge_base"}
        with open(path / "config.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    def _touch_meta(self, path: Path, **kwargs: Any) -> None:
        meta = self._read_meta(path) or {}
        meta["updated_at"] = _now()
        for k, v in kwargs.items():
            meta[k] = v
        if "file_count" not in kwargs:
            data = path / "data"
            meta["file_count"] = len(list(data.glob("*"))) if data.exists() else 0
        self._write_meta(path, meta)

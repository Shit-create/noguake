"""不挂科神器 Web 应用 — FastAPI 后端。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from src.paths import app_root, static_dir, user_data_root

ROOT = app_root()
sys.path.insert(0, str(ROOT))

from src.logger import setup_logging

setup_logging(log_dir=user_data_root() / "logs")

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from assets.build_meta import APP_NAME, APP_VERSION
from src.library_manager import LibraryManager
from src.quiz_service import build_library, search_question

app = FastAPI(title=APP_NAME, version=APP_VERSION)
mgr = LibraryManager()

_build_cooldowns: dict[str, float] = {}
_BUILD_COOLDOWN_S = 30

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8765", "http://localhost:8765", "http://127.0.0.1:8100"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC = static_dir()


class CreateLibraryBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    course_name: str = ""


class SearchBody(BaseModel):
    query: str = Field(..., min_length=3)


class BatchSearchBody(BaseModel):
    queries: list[str] = Field(..., min_length=1, max_length=20)


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/libraries")
async def list_libraries():
    return {"libraries": mgr.list_libraries()}


@app.post("/api/libraries")
async def create_library(body: CreateLibraryBody):
    lib = mgr.create_library(body.name, body.course_name)
    return {"library": lib}


@app.delete("/api/libraries/{lib_id}")
async def delete_library(lib_id: str):
    if not mgr.delete_library(lib_id):
        raise HTTPException(404, "题库不存在")
    return {"ok": True}


@app.get("/api/libraries/{lib_id}")
async def get_library(lib_id: str):
    lib = mgr.get_library(lib_id)
    if not lib:
        raise HTTPException(404, "题库不存在")
    lib["files"] = mgr.list_files(lib_id)
    return {"library": lib}


@app.get("/api/libraries/{lib_id}/files")
async def list_files(lib_id: str):
    if not mgr.get_library(lib_id):
        raise HTTPException(404, "题库不存在")
    return {"files": mgr.list_files(lib_id)}


@app.post("/api/libraries/{lib_id}/upload")
async def upload_file(lib_id: str, file: UploadFile = File(...)):
    if not mgr.get_library(lib_id):
        raise HTTPException(404, "题库不存在")
    if ".." in (file.filename or "") or "/" in (file.filename or "") or "\\" in (file.filename or ""):
        raise HTTPException(400, "文件名不能包含路径符号")
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "单文件不能超过 50MB")
    try:
        name = mgr.save_upload(lib_id, file.filename or "upload.pdf", content)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"filename": name, "files": mgr.list_files(lib_id)}


@app.delete("/api/libraries/{lib_id}/files/{filename}")
async def delete_file(lib_id: str, filename: str):
    if not mgr.delete_file(lib_id, filename):
        raise HTTPException(404, "文件不存在")
    return {"files": mgr.list_files(lib_id)}


@app.post("/api/libraries/{lib_id}/build")
async def build(lib_id: str):
    if not mgr.get_library(lib_id):
        raise HTTPException(404, "题库不存在")
    last = _build_cooldowns.get(lib_id, 0)
    elapsed = time.monotonic() - last
    if elapsed < _BUILD_COOLDOWN_S:
        raise HTTPException(429, f"请等待 {_BUILD_COOLDOWN_S - elapsed:.0f} 秒后再构建")
    try:
        result = build_library(lib_id, manager=mgr)
        _build_cooldowns[lib_id] = time.monotonic()
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"构建失败: {e}") from e
    return result


@app.post("/api/libraries/{lib_id}/search")
async def search(lib_id: str, body: SearchBody):
    if not mgr.get_library(lib_id):
        raise HTTPException(404, "题库不存在")
    try:
        return search_question(lib_id, body.query, manager=mgr)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.post("/api/libraries/{lib_id}/batch-search")
async def batch_search(lib_id: str, body: BatchSearchBody):
    if not mgr.get_library(lib_id):
        raise HTTPException(404, "题库不存在")
    results = []
    skipped = 0
    for query in body.queries:
        q = query.strip()
        if not q or len(q) < 3:
            skipped += 1
            continue
        try:
            results.append(search_question(lib_id, q, manager=mgr))
        except Exception as e:
            results.append({"found": False, "message": str(e), "question": None})
    return {"results": results, "total": len(results), "skipped": skipped}


app.mount("/static", StaticFiles(directory=STATIC), name="static")

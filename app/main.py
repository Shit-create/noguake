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
from src.license_manager import check_license, activate as activate_license, deactivate as deactivate_license, get_machine_id as license_machine_id, get_short_machine_id
from src.library_manager import LibraryManager
from src.quiz_service import build_library, search_question

app = FastAPI(title=APP_NAME, version=APP_VERSION)
mgr = LibraryManager()

_build_cooldowns: dict[str, float] = {}
_BUILD_COOLDOWN_S = 30

from collections import defaultdict
import time as _time

_rate_limits: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # 1 minute
_RATE_LIMIT_MAX = 30     # max requests per window

def _check_rate_limit(client_ip: str) -> bool:
    """简单的滑动窗口限流。"""
    now = _time.monotonic()
    window = _rate_limits[client_ip]
    window[:] = [t for t in window if now - t < _RATE_LIMIT_WINDOW]
    if len(window) >= _RATE_LIMIT_MAX:
        return False
    window.append(now)
    return True


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



# ============================================================
# 激活码 API
# ============================================================

@app.get("/api/license/status")
async def license_status():
    """获取当前激活状态。"""
    status = check_license()
    return status


@app.post("/api/license/activate")
async def license_activate(body: dict):
    """激活产品。"""
    code = body.get("code", "").strip()
    if not code:
        raise HTTPException(400, "请输入激活码")
    ok, msg = activate_license(code)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg, "status": check_license()}


@app.post("/api/license/deactivate")
async def license_deactivate():
    """卸载激活（换机器时使用）。"""
    deactivate_license()
    return {"ok": True}


@app.get("/api/license/machine-id")
async def license_machine_id_endpoint():
    """获取当前机器 ID（供用户复制发给客服）。"""
    return {"machine_id": license_machine_id(), "short_id": get_short_machine_id()}



# ============================================================
# 备份导出 API
# ============================================================

@app.post("/api/libraries/{lib_id}/export")
async def export_library(lib_id: str):
    """导出题库为 ZIP 文件（含题库数据和索引）。"""
    import io
    import zipfile
    from fastapi.responses import StreamingResponse

    if not mgr.get_library(lib_id):
        raise HTTPException(404, "题库不存在")

    lib_path = mgr.root / lib_id
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in lib_path.rglob("*"):
            if f.is_file():
                arcname = str(f.relative_to(lib_path))
                zf.write(f, arcname)
    buf.seek(0)

    lib_name = mgr.get_library(lib_id).get("name", lib_id)
    safe_name = "".join(c for c in lib_name if c.isalnum() or c in "._- ")[:30]
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="noguake_{safe_name}.zip"'
        },
    )


@app.post("/api/libraries/{lib_id}/import")
async def import_library(lib_id: str, file: UploadFile = File(...)):
    """从 ZIP 文件导入题库。"""
    import zipfile
    import io
    import shutil

    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(400, "请上传 .zip 格式的备份文件")

    content = await file.read()
    if len(content) > 200 * 1024 * 1024:
        raise HTTPException(400, "备份文件不能超过 200MB")

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            # 安全检查：防止 zip slip 攻击
            lib_path = mgr.root / lib_id
            for member in zf.namelist():
                member_path = (lib_path / member).resolve()
                if not str(member_path).startswith(str(lib_path.resolve())):
                    raise HTTPException(400, "备份文件包含非法路径")
            
            zf.extractall(lib_path)
    except zipfile.BadZipFile:
        raise HTTPException(400, "无效的 ZIP 文件")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"导入失败，请检查文件格式")

    # 刷新元数据
    mgr.update_build_stats(lib_id, status="imported")
    return {"ok": True, "message": "导入成功"}


@app.get("/api/health")
async def health():
    """健康检查。"""
    status = check_license()
    return {
        "status": "ok",
        "version": APP_VERSION,
        "licensed": status.get("licensed", False),
        "trial": status.get("trial", False),
        "days_left": status.get("days_left", 0),
    }


@app.get("/")
async def index():
    status = check_license()
    if not status.get("licensed") and not status.get("trial"):
        return FileResponse(STATIC / "activate.html")
    return FileResponse(STATIC / "index.html")


@app.get("/activate")
async def activate_page():
    """激活页面。"""
    return FileResponse(STATIC / "activate.html")


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
        # Clean up old cooldown entries (prevent unbounded growth)
        now = time.monotonic()
        stale = [k for k, v in _build_cooldowns.items() if now - v > 300]
        for k in stale:
            del _build_cooldowns[k]

    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, "构建失败，请检查文件格式后重试") from e
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
        raise HTTPException(500, "查询失败，请稍后重试") from e


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

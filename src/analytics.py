"""
使用统计与错误上报（可选，用户可关闭）。

设计原则：
- 默认关闭，需用户主动开启
- 不上传任何题目内容或个人数据
- 仅上报：版本号、激活状态、使用次数、错误类型
"""

from __future__ import annotations

import json
import platform
import threading
import time
from pathlib import Path
from typing import Any

import requests

from assets.build_meta import APP_VERSION

# 统计服务端点（自建或使用简单的 HTTP 接收端）
# 可以换成你自己的服务器
TELEMETRY_URL = ""  # 留空则不上报

# 本地统计文件
_stats_file = None
_stats_lock = threading.Lock()

# 匿名统计数据结构
_stats: dict[str, Any] = {
    "version": APP_VERSION,
    "platform": platform.system(),
    "first_run": 0,
    "total_runs": 0,
    "total_queries": 0,
    "total_builds": 0,
    "total_libraries": 0,
    "errors": {},
    "licensed": False,
    "last_report": 0,
}


def _get_stats_file() -> Path:
    from src.paths import user_data_root
    return user_data_root() / ".usage_stats"


def init_analytics() -> None:
    """初始化统计（应用启动时调用一次）。"""
    global _stats
    sf = _get_stats_file()
    sf.parent.mkdir(parents=True, exist_ok=True)

    if sf.exists():
        try:
            saved = json.loads(sf.read_text())
            _stats.update(saved)
        except Exception:
            pass

    now = int(time.time())
    if _stats["first_run"] == 0:
        _stats["first_run"] = now

    _stats["total_runs"] += 1
    _save_stats()


def track_query() -> None:
    """记录一次查询。"""
    with _stats_lock:
        _stats["total_queries"] += 1
    _maybe_save()


def track_build() -> None:
    """记录一次构建。"""
    with _stats_lock:
        _stats["total_builds"] += 1
    _maybe_save()


def track_error(error_type: str) -> None:
    """记录错误。"""
    with _stats_lock:
        _stats["errors"][error_type] = _stats["errors"].get(error_type, 0) + 1
    _maybe_save()


def track_library_created() -> None:
    """记录题库创建。"""
    with _stats_lock:
        _stats["total_libraries"] += 1
    _maybe_save()


def _maybe_save() -> None:
    """每 10 次变更写一次磁盘。"""
    total = _stats["total_queries"] + _stats["total_builds"] + _stats["total_runs"]
    if total % 10 == 0:
        _save_stats()


def _save_stats() -> None:
    """保存统计到本地。"""
    try:
        sf = _get_stats_file()
        sf.write_text(json.dumps(_stats, ensure_ascii=False, indent=2))
    except Exception:
        pass


def get_stats() -> dict:
    """获取当前统计数据。"""
    return dict(_stats)


def report_to_server() -> bool:
    """
    上报匿名统计到服务器（如果配置了 TELEMETRY_URL）。
    不上传敏感信息。
    """
    if not TELEMETRY_URL:
        return False

    try:
        payload = {
            "v": _stats["version"],
            "plat": _stats["platform"],
            "runs": _stats["total_runs"],
            "queries": _stats["total_queries"],
            "builds": _stats["total_builds"],
            "libs": _stats["total_libraries"],
            "licensed": _stats["licensed"],
            "errors": _stats["errors"],
        }
        r = requests.post(TELEMETRY_URL, json=payload, timeout=5)
        if r.status_code == 200:
            _stats["last_report"] = int(time.time())
            _save_stats()
            return True
    except Exception:
        pass
    return False

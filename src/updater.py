"""
自动更新检查模块。
通过 GitHub Releases 检查新版本，通知用户更新。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from assets.build_meta import APP_VERSION

# GitHub 仓库信息（打包时替换为你的仓库）
UPDATE_REPO = "your-username/noguake"
UPDATE_CHECK_URL = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"

# 检查间隔（秒），默认 24 小时
CHECK_INTERVAL = 86400

_last_check_file = None


def _get_check_file() -> Path:
    from src.paths import user_data_root
    return user_data_root() / ".update_check"


def check_for_updates(force: bool = False) -> dict[str, Any]:
    """
    检查是否有新版本。
    
    返回:
        {
            "has_update": bool,
            "current": str,
            "latest": str,
            "url": str,
            "body": str,
            "error": str | None,
        }
    """
    result = {
        "has_update": False,
        "current": APP_VERSION,
        "latest": APP_VERSION,
        "url": "",
        "body": "",
        "error": None,
    }

    # 节流：24 小时内不重复检查
    cf = _get_check_file()
    if not force and cf.exists():
        try:
            last = json.loads(cf.read_text())
            if time.time() - last.get("t", 0) < CHECK_INTERVAL:
                return last.get("result", result)
        except Exception:
            pass

    try:
        r = requests.get(UPDATE_CHECK_URL, timeout=10, headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"Noguake/{APP_VERSION}",
        })
        if r.status_code == 200:
            release = r.json()
            latest_tag = release.get("tag_name", "").lstrip("v")
            
            # 简单版本比较（支持 x.y.z 格式）
            if _version_greater(latest_tag, APP_VERSION):
                result["has_update"] = True
                result["latest"] = latest_tag
                result["url"] = release.get("html_url", "")
                result["body"] = release.get("body", "")[:500]
        elif r.status_code == 403:
            result["error"] = "API 限流，稍后重试"
        elif r.status_code == 404:
            result["error"] = "未找到更新信息"
        else:
            result["error"] = f"检查失败 ({r.status_code})"
    except requests.ConnectionError:
        result["error"] = "网络不可用"
    except Exception as e:
        result["error"] = str(e)[:100]

    # 缓存结果
    try:
        cf.parent.mkdir(parents=True, exist_ok=True)
        cf.write_text(json.dumps({"t": time.time(), "result": result}))
    except Exception:
        pass

    return result


def _version_greater(a: str, b: str) -> bool:
    """比较版本号 a > b。"""
    try:
        parts_a = [int(x) for x in a.split(".")]
        parts_b = [int(x) for x in b.split(".")]
        # 补齐长度
        while len(parts_a) < len(parts_b):
            parts_a.append(0)
        while len(parts_b) < len(parts_a):
            parts_b.append(0)
        return parts_a > parts_b
    except ValueError:
        return a != b

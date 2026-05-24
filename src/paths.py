"""应用根目录：开发环境 vs 安装包（PyInstaller）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_root() -> Path:
    """程序安装目录（含 exe、静态资源、默认配置）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_root() -> Path:
    """用户数据目录（题库、索引），安装/升级不覆盖。"""
    if is_frozen():
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Noguake"
        base.mkdir(parents=True, exist_ok=True)
        return base
    return app_root()


def libraries_dir() -> Path:
    d = user_data_root() / "libraries"
    d.mkdir(parents=True, exist_ok=True)
    return d


def static_dir() -> Path:
    return app_root() / "app" / "static"

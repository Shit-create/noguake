"""项目统一日志模块。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(
    log_dir: Path | None = None,
    level: int = logging.INFO,
) -> None:
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler: logging.Handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(fmt)
    root = logging.getLogger("noguake")
    root.setLevel(level)
    root.addHandler(handler)

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)

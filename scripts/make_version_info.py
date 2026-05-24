#!/usr/bin/env python3
"""根据 assets/build_meta.py 生成 PyInstaller 用的 version_info.txt。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META_PATH = ROOT / "assets" / "build_meta.py"
OUT = ROOT / "assets" / "version_info.txt"


def load_meta():
    spec = importlib.util.spec_from_file_location("build_meta", META_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    m = load_meta()
    vt = m.APP_VERSION_TUPLE
    vs = m.APP_VERSION
    content = f"""# UTF-8 — auto-generated, do not edit by hand
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={vt},
    prodvers={vt},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'080404B0',
        [StringStruct(u'CompanyName', u'{m.COMPANY}'),
        StringStruct(u'FileDescription', u'{m.APP_NAME}'),
        StringStruct(u'FileVersion', u'{vs}'),
        StringStruct(u'InternalName', u'{m.APP_NAME_EN}'),
        StringStruct(u'LegalCopyright', u'{m.COPYRIGHT}'),
        StringStruct(u'OriginalFilename', u'{m.EXE_NAME}'),
        StringStruct(u'ProductName', u'{m.APP_NAME}'),
        StringStruct(u'ProductVersion', u'{vs}')])
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

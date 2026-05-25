"""
机器指纹模块：生成不可逆硬件标识，用于激活码绑定。

采集策略：
- 主板 UUID (wmic) — 最稳定
- 主网卡 MAC — 备选
- 组合后 SHA256 哈希，不可逆推出原始硬件信息
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> str:
    """运行系统命令并返回 stdout，失败返回空字符串。"""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            **({"shell": True} if sys.platform == "win32" else {}),
        )
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _windows_fingerprint() -> str:
    """Windows: 主板 UUID + 物理网卡 MAC。"""
    parts = []

    uuid_out = _run(["wmic", "csproduct", "get", "UUID"]).split("\n")
    for line in uuid_out:
        line = line.strip()
        if line and line.lower() != "uuid" and len(line) > 8:
            parts.append(line)
            break

    mac_out = _run([
        "wmic", "nic", "where", "PhysicalAdapter=True", "get", "MACAddress",
    ]).split("\n")
    for line in mac_out:
        mac = line.strip().replace(":", "").replace("-", "").upper()
        if len(mac) == 12:
            parts.append(mac)
            break

    if not parts:
        parts.append(platform.node())
        vol_out = _run(["wmic", "diskdrive", "get", "SerialNumber"]).split("\n")
        for line in vol_out:
            s = line.strip()
            if s and s.lower() != "serialnumber" and len(s) > 3:
                parts.append(s)
                break

    return "|".join(parts)


def _linux_fingerprint() -> str:
    """Linux: machine-id + 主网卡 MAC。"""
    parts = []
    for p in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
        mp = Path(p)
        if mp.exists():
            parts.append(mp.read_text().strip())
            break

    for iface in sorted(Path("/sys/class/net").iterdir()):
        if iface.name == "lo":
            continue
        addr = iface / "address"
        if addr.exists():
            mac = addr.read_text().strip().replace(":", "").upper()
            if len(mac) == 12 and mac != "000000000000":
                parts.append(mac)
                break

    if not parts:
        parts.append(platform.node())
    return "|".join(parts)


def _darwin_fingerprint() -> str:
    """macOS: 硬件 UUID + 主网卡 MAC。"""
    parts = []
    hw = _run(["ioreg", "-d2", "-c", "IOPlatformExpertDevice"])
    for line in hw.split("\n"):
        if "IOPlatformUUID" in line:
            val = line.split('"')[-2] if '"' in line else ""
            if val:
                parts.append(val)
                break

    if_out = _run(["ifconfig", "en0"]).split("\n")
    for line in if_out:
        if "ether" in line:
            mac = line.split("ether")[-1].strip().replace(":", "").upper()
            if len(mac) == 12:
                parts.append(mac)
                break

    if not parts:
        parts.append(platform.node())
    return "|".join(parts)


def get_machine_id() -> str:
    """返回 64 字符的稳定机器指纹（SHA256）。"""
    if sys.platform == "win32":
        raw = _windows_fingerprint()
    elif sys.platform == "darwin":
        raw = _darwin_fingerprint()
    else:
        raw = _linux_fingerprint()

    salt = "noguake-m1d-2024-s4lt-v1"
    return hashlib.sha256(f"{raw}|{salt}".encode()).hexdigest()


def get_short_id() -> str:
    """8 字符短 ID，用于显示。"""
    return get_machine_id()[:8].upper()

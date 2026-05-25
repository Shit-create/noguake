"""
激活码验证与授权管理。支持：
- Ed25519 离线签名验证（无需联网）
- 机器指纹绑定
- 有效期检查
- 试用期管理（首次运行 7 天）
- 防篡改（HMAC 签名保护激活状态文件）
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ============================================================
# 公钥 — 编译时嵌入，对应 scripts/gen_license.py 中的私钥
# 如果你重新生成了密钥对，必须同时更新此处和 gen_license.py
# ============================================================
_PUBLIC_KEY_HEX = "1eaa0f3eb2139f204c8280089382c48e2e3384a3fb9d9e00ad511a32e8fa7274"

# 试用期天数
TRIAL_DAYS = 7

# 激活状态文件名
_LICENSE_FILE = "license.dat"

# HMAC 密钥（派生自公钥，防篡改激活文件）
_HMAC_KEY = hashlib.sha256(_PUBLIC_KEY_HEX.encode()).digest()


@dataclass
class LicenseInfo:
    machine_id: str       # 绑定机器
    issued_at: int        # 签发时间戳
    expires_at: int       # 过期时间戳（0=永久）
    features: list[str]   # 功能列表
    signature: bytes      # Ed25519 签名


def _crypto_available() -> bool:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        return True
    except ImportError:
        return False


def _verify_signature(payload: bytes, signature: bytes) -> bool:
    """Ed25519 签名验证。"""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature

    try:
        pub_bytes = bytes.fromhex(_PUBLIC_KEY_HEX)
        pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
        pub_key.verify(signature, payload)
        return True
    except (InvalidSignature, ValueError):
        return False


def _license_path() -> Path:
    """激活文件存储路径（用户数据目录）。"""
    from src.paths import user_data_root
    return user_data_root() / _LICENSE_FILE


def _sign_state(data: bytes) -> str:
    """HMAC-SHA256 签名。"""
    return hmac.new(_HMAC_KEY, data, hashlib.sha256).hexdigest()


def _encode_license(info: LicenseInfo) -> str:
    """序列化激活码（base32，去混淆）。"""
    payload = json.dumps({
        "m": info.machine_id,
        "i": info.issued_at,
        "e": info.expires_at,
        "f": info.features,
    }, separators=(",", ":"))
    
    sig_b64 = base64.b64encode(info.signature).decode("ascii")
    combined = f"{payload}|{sig_b64}"
    
    # Base32 编码（易读，不易输错）
    # 每 5 字符一组，用 - 连接
    raw = base64.b32encode(combined.encode()).decode("ascii").rstrip("=")
    groups = [raw[i:i+5] for i in range(0, len(raw), 5)]
    return "-".join(groups)


def _decode_license(code: str) -> LicenseInfo | None:
    """反序列化激活码。"""
    try:
        code = code.replace("-", "").replace(" ", "").upper()
        # 补齐 base32 padding
        padding = 8 - (len(code) % 8)
        if padding != 8:
            code += "=" * padding
        
        combined = base64.b32decode(code).decode("utf-8")
        payload_str, sig_b64 = combined.split("|", 1)
        payload = json.loads(payload_str)
        signature = base64.b64decode(sig_b64)
        
        return LicenseInfo(
            machine_id=payload["m"],
            issued_at=payload["i"],
            expires_at=payload["e"],
            features=payload.get("f", []),
            signature=signature,
        )
    except Exception:
        return None


# ============================================================
# 公共 API
# ============================================================

def check_crypto() -> bool:
    """检查 cryptography 库是否安装。"""
    if not _crypto_available():
        return False
    return True


def get_machine_id() -> str:
    """获取当前机器指纹。"""
    from src.machine_id import get_machine_id as _mid
    return _mid()


def get_short_machine_id() -> str:
    """获取短机器 ID（用于显示）。"""
    from src.machine_id import get_short_id
    return get_short_id()


def get_trial_info() -> dict:
    """获取试用状态。"""
    trial_file = _license_path().with_suffix(".trial")
    now = int(time.time())
    
    if trial_file.exists():
        try:
            data = json.loads(trial_file.read_text())
            started = data.get("s", 0)
            days_left = max(0, TRIAL_DAYS - (now - started) // 86400)
            return {
                "trial_active": days_left > 0,
                "days_left": days_left,
                "started_at": started,
                "expires_at": started + TRIAL_DAYS * 86400,
            }
        except Exception:
            pass
    
    # 首次试用
    trial_file.parent.mkdir(parents=True, exist_ok=True)
    trial_file.write_text(json.dumps({"s": now}))
    return {
        "trial_active": True,
        "days_left": TRIAL_DAYS,
        "started_at": now,
        "expires_at": now + TRIAL_DAYS * 86400,
    }


def activate(code: str) -> tuple[bool, str]:
    """
    验证并保存激活码。
    返回 (成功, 消息)。
    """
    if not check_crypto():
        return False, "缺少 cryptography 库，请运行: pip install cryptography"

    info = _decode_license(code)
    if info is None:
        return False, "激活码格式无效，请检查是否完整复制"

    # 验证签名
    payload = json.dumps({
        "m": info.machine_id,
        "i": info.issued_at,
        "e": info.expires_at,
        "f": info.features,
    }, separators=(",", ":")).encode()
    
    if not _verify_signature(payload, info.signature):
        return False, "激活码验证失败 — 签名无效（可能被篡改或伪造）"

    # 验证机器绑定
    current_mid = get_machine_id()
    if info.machine_id != current_mid:
        return False, (
            f"激活码绑定的机器不匹配。\n"
            f"当前机器 ID: {current_mid[:8]}...\n"
            f"激活码绑定: {info.machine_id[:8]}...\n"
            f"请联系客服提供新的激活码"
        )

    # 验证是否过期
    if info.expires_at > 0 and int(time.time()) > info.expires_at:
        from datetime import datetime
        exp_str = datetime.fromtimestamp(info.expires_at).strftime("%Y-%m-%d")
        return False, f"激活码已过期（{exp_str}），请联系客服续费"

    # 保存激活状态
    state = {
        "code_hash": hashlib.sha256(code.encode()).hexdigest()[:16],
        "machine_id": current_mid,
        "issued_at": info.issued_at,
        "expires_at": info.expires_at,
        "features": info.features,
        "activated_at": int(time.time()),
    }
    state_json = json.dumps(state, separators=(",", ":"))
    state_sig = _sign_state(state_json.encode())
    
    lp = _license_path()
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_text(json.dumps({
        "state": state,
        "sig": state_sig,
    }, separators=(",", ":")))

    # 删除试用文件
    trial_file = _license_path().with_suffix(".trial")
    if trial_file.exists():
        trial_file.unlink()

    return True, "激活成功！"


def check_license() -> dict:
    """
    检查当前激活状态。
    返回 {"licensed": bool, "trial": bool, "message": str, "features": list, ...}
    """
    result = {
        "licensed": False,
        "trial": False,
        "days_left": 0,
        "message": "",
        "features": [],
        "machine_id": get_short_machine_id(),
    }

    # 先检查正式激活
    lp = _license_path()
    if lp.exists():
        try:
            data = json.loads(lp.read_text())
            state = data["state"]
            sig = data["sig"]
            
            # 防篡改验证
            expected_sig = _sign_state(
                json.dumps(state, separators=(",", ":")).encode()
            )
            if sig != expected_sig:
                result["message"] = "激活文件已损坏，请重新激活"
                return result
            
            # 机器变更检测
            if state["machine_id"] != get_machine_id():
                result["message"] = f"硬件变更，激活失效。机器 ID: {get_short_machine_id()}"
                return result
            
            # 过期检查
            if state["expires_at"] > 0 and int(time.time()) > state["expires_at"]:
                from datetime import datetime
                exp = datetime.fromtimestamp(state["expires_at"]).strftime("%Y-%m-%d")
                result["message"] = f"授权已过期（{exp}），请续费"
                result["days_left"] = 0
                return result
            
            # 有效！
            result["licensed"] = True
            result["features"] = state.get("features", [])
            if state["expires_at"] > 0:
                result["days_left"] = max(0, (state["expires_at"] - int(time.time())) // 86400)
            else:
                result["days_left"] = -1  # 永久授权
            result["message"] = "已激活" + ("（永久）" if result["days_left"] == -1 else "")
            return result
            
        except Exception:
            pass

    # 未激活 — 检查试用
    trial_info = get_trial_info()
    if trial_info["trial_active"]:
        result["trial"] = True
        result["days_left"] = trial_info["days_left"]
        result["message"] = f"试用期还剩 {trial_info['days_left']} 天"
        return result

    result["message"] = "试用期已结束，请输入激活码"
    return result


def is_licensed() -> bool:
    """快速检查是否已激活（包括试用）。"""
    try:
        status = check_license()
        return status["licensed"] or status["trial"]
    except Exception:
        return True  # 出错时放行


def get_expiry_days() -> int:
    """获取剩余天数。-1=永久, 0=过期, >0=剩余天数。"""
    status = check_license()
    return status.get("days_left", 0)


def deactivate() -> bool:
    """删除激活状态（用户卸载时调用）。"""
    lp = _license_path()
    if lp.exists():
        lp.unlink()
        return True
    return False

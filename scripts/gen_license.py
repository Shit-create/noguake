#!/usr/bin/env python3
"""
激活码生成器 — 卖家工具。
⚠️ 此文件绝不能分发给用户！

使用方式：
  python scripts/gen_license.py --machine-id <64位机器ID> --days 365
  python scripts/gen_license.py --machine-id <64位机器ID> --permanent

输出：复制激活码发给客户即可。
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

# 确保 src 在 Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ⚠️ 私钥 — 绝不能泄露！
# 如果更换密钥对，必须同时更新 src/license_manager.py 中的 _PUBLIC_KEY_HEX
_PRIVATE_KEY_HEX = "620b948156d2bc30d764928122ad1bfeb69c5d2bb3a828ecd6c0a071e8be41c5"

# ====== 密钥管理 ======

def _new_keypair():
    """生成新的 Ed25519 密钥对（一次性操作）。"""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_bytes = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_bytes = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)

    print("=" * 60)
    print("新密钥对已生成（请妥善保管！）")
    print("=" * 60)
    print(f"\n私钥（写入 scripts/gen_license.py）:")
    print(f'_PRIVATE_KEY_HEX = "{priv_bytes.hex()}"')
    print(f"\n公钥（写入 src/license_manager.py）:")
    print(f'_PUBLIC_KEY_HEX = "{pub_bytes.hex()}"')
    print("=" * 60)


def _sign_payload(payload: bytes) -> bytes:
    """Ed25519 签名。"""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    priv_bytes = bytes.fromhex(_PRIVATE_KEY_HEX)
    private_key = Ed25519PrivateKey.from_private_bytes(priv_bytes)
    return private_key.sign(payload)


# ====== 激活码生成 ======

def generate_license(
    machine_id: str,
    days: int = 0,
    features: list[str] | None = None,
) -> str:
    """
    生成激活码。
    
    Args:
        machine_id: 客户的 64 位机器指纹（客户在软件里可以看到）
        days: 有效期天数（0 = 永久授权）
        features: 功能列表，如 ["full"]
    
    Returns:
        激活码字符串（XXXXX-XXXXX-... 格式）
    """
    now = int(time.time())
    expires_at = now + days * 86400 if days > 0 else 0
    
    payload = json.dumps({
        "m": machine_id,
        "i": now,
        "e": expires_at,
        "f": features or ["full"],
    }, separators=(",", ":")).encode()
    
    signature = _sign_payload(payload)
    sig_b64 = base64.b64encode(signature).decode("ascii")
    
    combined = f"{payload.decode()}|{sig_b64}"
    raw = base64.b32encode(combined.encode()).decode("ascii").rstrip("=")
    groups = [raw[i:i+5] for i in range(0, len(raw), 5)]
    code = "-".join(groups)
    
    return code


# ====== CLI ======

def main():
    parser = argparse.ArgumentParser(description="不挂科神器 - 激活码生成器")
    parser.add_argument("--machine-id", "-m",
                        help="客户机器 ID（64 位十六进制）")
    parser.add_argument("--days", "-d", type=int, default=365,
                        help="有效期天数（默认 365，0=永久）")
    parser.add_argument("--permanent", "-p", action="store_true",
                        help="永久授权")
    parser.add_argument("--features", "-f", nargs="*", default=["full"],
                        help="功能（默认 full）")
    parser.add_argument("--new-keypair", action="store_true",
                        help="生成新密钥对（一次性）")
    parser.add_argument("--batch", type=str,
                        help="从文件批量生成（每行一个 machine_id）")
    
    args = parser.parse_args()
    
    if args.new_keypair:
        _new_keypair()
        return

    if not args.machine_id:
        parser.error("--machine-id is required (unless using --new-keypair)")

    # 验证 machine_id
    mid = args.machine_id.strip().lower()
    if len(mid) != 64 or not all(c in "0123456789abcdef" for c in mid):
        print("错误：machine-id 必须是 64 位十六进制字符串")
        print("客户可在软件的激活页面找到此 ID")
        sys.exit(1)
    
    days = 0 if args.permanent else args.days
    
    if args.batch:
        batch_file = Path(args.batch)
        if not batch_file.exists():
            print(f"错误：文件不存在 {args.batch}")
            sys.exit(1)
        
        lines = [l.strip() for l in batch_file.read_text().splitlines() if l.strip()]
        print(f"批量生成 {len(lines)} 个激活码...\n")
        
        output_lines = []
        for mid_line in lines:
            mid_line = mid_line.lower()
            if len(mid_line) != 64 or not all(c in "0123456789abcdef" for c in mid_line):
                print(f"  跳过无效 ID: {mid_line[:16]}...")
                continue
            code = generate_license(mid_line, days, args.features)
            output_lines.append(f"{mid_line}\t{code}")
            print(f"  {mid_line[:8]}... => {code[:30]}...")
        
        out_path = batch_file.with_suffix(".licenses.txt")
        out_path.write_text("\n".join(output_lines))
        print(f"\n已保存到 {out_path}")
    else:
        code = generate_license(mid, days, args.features)
        
        print()
        print("=" * 60)
        print(f"  激活码 (有效期: {'永久' if days == 0 else f'{days} 天'})")
        print("=" * 60)
        print()
        print(f"  {code}")
        print()
        print("=" * 60)
        print(f"  机器 ID: {mid}")
        print(f"  功能: {args.features}")
        if days > 0:
            exp = time.strftime("%Y-%m-%d", time.localtime(time.time() + days * 86400))
            print(f"  过期时间: {exp}")
        print("  将此激活码发给客户即可")
        print("=" * 60)

if __name__ == "__main__":
    main()

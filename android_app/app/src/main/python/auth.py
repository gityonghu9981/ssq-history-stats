# -*- coding: utf-8 -*-
"""激活码验证模块（Android 端，纯标准库实现）
内嵌公钥 (N, E)，只做验证、没有生成能力。
生成激活码的私钥仅存在于主人电脑的生成器工具中。
"""
import hashlib

# 公钥（来自桌面工具 public_key.txt，勿改）
PUB_N = 26442984938630118749641666576357934628922320308842544827511395037964162158067932037010217731711471798892978129038091211213041044880385272442103138148593178989613965086296680353000378203445574260454031279464999433076240054744078057112599465345443090533994723740381755326454967437397055506137728896755753945137973693689652673558159665770251061593559514387559378536919523320106709950008625680398458076353392487385457731647584491261132392830379388221657493239713612034802285610303771206079992029361295234514883056780256313397395951203664156529222420358977512700256903058731581126535796027681784201578580049707451112918117
PUB_E = 65537

_CHARS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CHAR_MAP = {c: i for i, c in enumerate(_CHARS)}
_ALIAS = {"O": "0", "I": "1", "L": "1"}  # 容错：O->0, I/L->1


def _b32decode(s: str) -> bytes:
    s = s.upper().replace("-", "").replace(" ", "")
    for k, v in _ALIAS.items():
        s = s.replace(k, v)
    acc = 0
    bits = 0
    out = bytearray()
    for ch in s:
        if ch not in _CHAR_MAP:
            raise ValueError("bad char")
        acc = (acc << 5) | _CHAR_MAP[ch]
        bits += 5
        if bits >= 8:
            bits -= 8
            out.append((acc >> bits) & 0xFF)
    return bytes(out)


def verify_activate(device_code: str, activate_code: str) -> bool:
    """校验激活码是否由主人私钥对本设备码签名。
    device_code 传原始设备标识（16 位 hex，大写，无前缀无分隔符）。
    """
    try:
        d = device_code.strip().upper().replace("SSQ", "").replace("-", "").replace(" ", "")
        if not d:
            return False
        sig = _b32decode(activate_code.strip())
        if len(sig) != 256:
            return False
        s = int.from_bytes(sig, "big")
        m = int.from_bytes(hashlib.sha256(("SSQ:" + d).encode()).digest(), "big")
        return pow(s, PUB_E, PUB_N) == m
    except Exception:
        return False

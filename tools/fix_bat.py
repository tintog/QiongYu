"""把 .bat 脚本统一为 GBK(CP936) + CRLF —— Windows 中文系统 CMD 的默认编码。

背景（三个坑，缺一不可）：
  - UTF-8 无 BOM + LF  → CMD 逐行粘连，满屏报"不是内部或外部命令"
  - UTF-8 有 BOM       → 首行变成 "BOM+@echo off"，同样报错
  - GBK + CRLF 无 BOM  → 与中文 Windows 控制台默认代码页一致，无需 chcp，最稳

本脚本幂等，可反复执行。编辑过 .bat 之后跑一次即可。

用法：
    python tools/fix_bat.py            # 处理项目根目录下的 install/start/stop.bat
"""

from pathlib import Path

# 项目根目录 = 本文件的上一级
BASE = Path(__file__).resolve().parent.parent

TARGETS = ("install.bat", "start.bat", "stop.bat")

# GBK 无法编码的符号 → ASCII 替代
REPLACE = {
    "\u26a0": "[警告]",   # ⚠
    "\u2714": "[OK]",     # ✔
    "\u2717": "[失败]",   # ✗
    "\u00b7": "-",        # ·
    "\u2022": "-",        # •
    "\u2026": "...",      # …
    "\u2192": "->",       # →
    "\u2014": "--",       # —
    "\u2500": "-",        # ─
    "\u2501": "-",        # ━
}


def read_any(path: Path) -> str:
    """按 UTF-8(BOM) / GBK 依次尝试解码，兼容中间态文件。"""
    raw = path.read_bytes()
    if raw[:3] == b"\xef\xbb\xbf":
        return raw[3:].decode("utf-8")
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def fix(path: Path) -> str:
    original = path.read_bytes()
    text = read_any(path)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 去掉 chcp 行（GBK 下不需要）
    text = "\n".join(
        ln for ln in text.split("\n") if not ln.strip().lower().startswith("chcp ")
    )

    # 替换 GBK 不兼容符号
    for k, v in REPLACE.items():
        text = text.replace(k, v)

    # 统一 CRLF 后按 GBK 写回，无 BOM
    path.write_bytes(text.replace("\n", "\r\n").encode("gbk", errors="replace"))

    out = path.read_bytes()
    crlf = out.count(b"\r\n")
    bare_lf = out.count(b"\x0a") - crlf
    return (
        f"{path.name}: {len(original)} -> {len(out)} bytes | "
        f"BOM={out[:3] == b'\xef\xbb\xbf'} | CRLF={crlf} | bare_LF={bare_lf}"
    )


if __name__ == "__main__":
    for name in TARGETS:
        p = BASE / name
        if not p.exists():
            print(f"{name}: 跳过（文件不存在）")
            continue
        print(fix(p))

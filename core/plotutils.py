# -*- coding: utf-8 -*-
"""跨平台中文字体设置 (Windows/macOS/Linux)。"""
from __future__ import annotations

import matplotlib
import matplotlib.font_manager as fm


def setup_chinese_font() -> None:
    """按平台偏好选择中文字体, 找不到则回退默认。"""
    cands = []
    for f in fm.findSystemFonts():
        name = f.lower()
        # Windows
        if "msyh" in name or "yahei" in name:
            cands.append((0, f))
        elif "simhei" in name:
            cands.append((1, f))
        elif "simsun" in name:
            cands.append((2, f))
        # macOS
        elif "pingfang" in name:
            cands.append((0, f))
        elif "hiragino" in name and "gb" in name:
            cands.append((1, f))
        elif "stheiti" in name:
            cands.append((2, f))
        elif "arial unicode" in name:
            cands.append((2, f))
    if cands:
        cands.sort()
        try:
            matplotlib.rcParams["font.sans-serif"] = [fm.FontProperties(fname=cands[0][1]).get_name()]
        except Exception:  # noqa: BLE001
            pass
    matplotlib.rcParams["axes.unicode_minus"] = False

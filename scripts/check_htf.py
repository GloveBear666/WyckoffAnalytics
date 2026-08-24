# -*- coding: utf-8 -*-
"""HTF 门控快速验证。"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.data import load_data
from core.signals import generate_signals, summarize_signals

h1 = load_data("BTC/USDT", "crypto", "1h")
h4 = load_data("BTC/USDT", "crypto", "4h")
d1 = load_data("BTC/USDT", "crypto", "1d")

for T in (0.3, 0.5):
    s_plain = generate_signals(h1, T=T)
    s_htf = generate_signals(h1, T=T, htf=h4)
    n1 = summarize_signals(s_plain)["signals"]
    n2 = summarize_signals(s_htf)["signals"]
    print(f"T={T} 1h plain={n1}  1h+4hHTF={n2}  (filtered={n1 - n2})")

s_1d = generate_signals(d1, T=0.5)
print("1d standalone:", summarize_signals(s_1d))
print("HTF_CHECK_OK")

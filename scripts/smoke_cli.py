# -*- coding: utf-8 -*-
"""CLI 冒烟 v2：引擎（全枚举精确）+ 全量回测（抽样加速）。"""
from db import DrawDB
from engine import SelectionEngine
from backtest import Backtest

db = DrawDB()
red = db.red_sequences()
blue = db.blue_sequences()

eng = SelectionEngine(red, blue, rng=None)
out = eng.run()
assert not out["无数据"]
assert len(out["大底"]) == 18
for k in range(1, 7):
    g = out["组"][f"结果{k}"]
    assert len(g["红球"]) in (6, 10), f"结果{k} 长度异常"
    assert 1 <= g["蓝球"] <= 16
assert len(out["组"]["结果1"]["红球"]) == 6
assert len(out["组"]["结果2"]["红球"]) == 10

import time
t0 = time.time()
bt = Backtest(red, blue, window=100, max_rounds=None, block_sample=1500)
res = bt.run()
dt = time.time() - t0
print(f"CLI冒烟OK 全量回测{res['回测期数']}期 耗时{dt:.0f}s "
      f"大底命中{res['大底平均命中']:.3f} 结果1红球{res['结果1']['平均红球命中']:.3f}")
db.close()

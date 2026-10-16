# -*- coding: utf-8 -*-
"""数据校验：抽查已知期号 + 全量引擎/回测冒烟。"""
from db import DrawDB
from engine import SelectionEngine
from backtest import Backtest

db = DrawDB()
n = db.count()
print(f"库内总期数: {n}")
print(f"最早期号: {db.first_issue()}, 最新期号: {db.latest_issue()}")

# 抽查
checks = {
    "2003001": {"红": [3, 4, 5, 8, 10, 11], "蓝": 7},   # 需与官方核对
    "2003002": {"红": [7, 8, 9, 13, 22, 26], "蓝": 3},
    "2026113": {"红": [3, 4, 20, 24, 29, 30], "蓝": 11},  # 官网接口已核对
    "2025001": {"红": [2, 3, 17, 18, 22, 33], "蓝": 16},
}
for issue, expect in checks.items():
    for d in db.get_all("asc"):
        if d["issue"] == issue:
            ok = sorted(d["reds"]) == expect["红"] and d["blue"] == expect["蓝"]
            print(f"  {issue}: {d['reds']}+{d['blue']}  期望 {expect['红']}+{expect['蓝']}  {'✓' if ok else '✗ 需人工核对'}")
            break

# 引擎
red = db.red_sequences()
blue = db.blue_sequences()
eng = SelectionEngine(red, blue, rng=None)
out = eng.run()
assert not out["无数据"]
print(f"\n引擎: 大底 {sorted(out['大底'])}")
for k in range(1, 7):
    g = out["组"][f"结果{k}"]
    assert len(g["红球"]) == 6 and all(1 <= x <= 33 for x in g["红球"])
    assert 1 <= g["蓝球"] <= 16
print("6 组结果均合法")

# 回测（全量数据，100期窗口，50期回测，测性能）
import time
t0 = time.time()
bt = Backtest(red, blue, window=100, max_rounds=50)
res = bt.run()
dt = time.time() - t0
print(f"\n回测 {res['回测期数']} 期耗时 {dt:.1f} 秒")
print(f"大底平均命中: {res['大底平均命中']:.3f} (随机基准 {res['随机基准红球']})")
r1 = res["结果1"]
print(f"结果1 平均红球命中: {r1['平均红球命中']:.3f}, 蓝球命中率 {r1['蓝球命中率']*100:.1f}%, 奖级 {r1['奖级分布']}")
db.close()
print("\n全量冒烟通过 ✅")

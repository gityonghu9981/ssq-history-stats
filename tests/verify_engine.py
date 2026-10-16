# -*- coding: utf-8 -*-
"""重构后引擎验证：投票层 + 双轨 + 6 组结果（含概率型集合）。"""
import os, sys
sys.path.insert(0, r'E:\双色球智能选号\app')
from db import DrawDB
from engine import SelectionEngine, check_forms
from backtest import Backtest
import random, time

db = DrawDB()
red = db.red_sequences()
blue = db.blue_sequences()

# ---- 引擎结构 ----
eng = SelectionEngine(red, blue, rng=random.Random(7))
out = eng.run()
print("== 6 组结果 ==")
NOTE = ("结果1", "结果3", "结果5")
for k in range(1, 7):
    g = out["组"][f"结果{k}"]
    key = f"结果{k}"
    if key in NOTE:  # 注单：严格 6 红不重复 + 1 蓝
        assert len(g["红球"]) == 6 and len(set(g["红球"])) == 6
        assert 1 <= g["蓝球"] <= 16
    else:            # 概率型集合：红球为评分集合（10码）+ 统计最优蓝球
        assert len(g["红球"]) == 10, f"{key} 红球应为10码集合, 实际{len(g['红球'])}"
        assert 1 <= g["蓝球"] <= 16
    print(f"{key}: {g['红球']} + {g['蓝球']:02d}  | {g['来源']}")

print("\n大底:", out["大底"], f"({len(out['大底'])}个)")
print("蓝球候选:", out["蓝球候选"], "| 区块重叠率:", round(out["投票"]["区块重叠率"], 3))
print("结果1 形态满足:", check_forms(out["组"]["结果1"]["红球"], out["形态"])[0])

# ---- 排除号 ----
eng2 = SelectionEngine(red, blue, rng=random.Random(3),
                       exclude_red={1, 2, 3, 33}, exclude_blue={16})
out2 = eng2.run()
for k in range(1, 7):
    g = out2["组"][f"结果{k}"]
    assert not (set(g["红球"]) & {1, 2, 3, 33})
    assert g["蓝球"] != 16
assert not (set(out2["大底"]) & {1, 2, 3, 33})
print("\n排除号验证通过")

# ---- 回测：全量模式正确性 + 抽样性能 ----
t0 = time.time()
bt_full = Backtest(red, blue, window=100, max_rounds=None, block_sample=1500)
res = bt_full.run()
dt = time.time() - t0
print(f"\n全量回测 {res['回测期数']} 期 耗时 {dt:.1f} 秒")
print(f"大底平均命中: {res['大底平均命中']:.3f} (随机 {res['随机基准红球']})")
for k in ("结果1", "结果2", "结果3", "结果4", "结果5", "结果6"):
    s = res[k]
    if s is None:
        continue
    prize = s.get("奖级分布", {})
    print(f"{k}: 平均红球命中 {s['平均红球命中']:.3f}, 蓝球命中率 {s['蓝球命中率']*100:.1f}%"
          + (f", 中奖 {sum(prize.values())} 次" if prize else ", 概率型集合无奖级"))
db.close()
print("\n引擎重构验证全部通过 ✅")

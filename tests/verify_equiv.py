# -*- coding: utf-8 -*-
"""等价性铁证：同一 200 期，单进程 vs 分块（2×100），结果逐项完全一致。"""
import os, sys
sys.path.insert(0, r'E:\双色球智能选号\app')
from db import DrawDB
from backtest import Backtest

db = DrawDB()
red = db.red_sequences()
blue = db.blue_sequences()
n = len(red)
window = 100
rounds = 200
begin = n - rounds

# 方式一：单进程连续 200 期
bt = Backtest(red, blue, window=window, max_rounds=rounds, block_sample=1500)
single = bt.run()

# 方式二：分块（2×100 期）再合并
raw1 = bt._run_range(begin, begin + 100)
raw2 = bt._run_range(begin + 100, n)
blocked = Backtest.merge_blocks([raw1, raw2], window)

print("单进程 200 期:")
print("  大底命中分布:", single["大底命中分布"])
print("  大底平均命中:", round(single["大底平均命中"], 6))
print("  结果1:", single["结果1"])
print("  结果2:", single["结果2"])
print("分块 2×100 期合并:")
print("  大底命中分布:", blocked["大底命中分布"])
print("  大底平均命中:", round(blocked["大底平均命中"], 6))
print("  结果1:", blocked["结果1"])
print("  结果2:", blocked["结果2"])

assert single == blocked, "分块与单进程结果不一致！"
print("\n✅ 单进程与分块结果逐项完全一致（准确率零损失，分块仅进程隔离）")
db.close()

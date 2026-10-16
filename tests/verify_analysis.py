# -*- coding: utf-8 -*-
"""最终分析交付前的第三轮综合验证。
覆盖：六组去重数稳定性、区块并列、熵权权重、模块17负值、蓝球候选使用、
FetchWorker假错误（close后调用）、import_csv缺列崩溃。"""
import os
import sys
import random
import tempfile
import csv

sys.path.insert(0, r"E:\双色球智能选号\app")
from db import DrawDB
from engine import SelectionEngine, mod17_kurtosis

DB = r"E:\双色球智能选号\dist\data\ssq.db"
db = DrawDB(DB)
rows = db.get_latest_n(200)
red_seq = [r["reds"] for r in rows]
blue_seq = [r["blue"] for r in rows]

print("=== 1. 多种子下六组去重数（结构性验证） ===")
for seed in (0, 42, 2026):
    eng = SelectionEngine(red_seq, blue_seq, rng=random.Random(seed), big_pool=18)
    out = eng.run()
    sets = {}
    for k in ("结果1", "结果2", "结果3", "结果4", "结果5", "结果6"):
        rr = tuple(sorted(out["组"][k]["红球"]))
        sets.setdefault(rr, []).append(k)
    bl = {out["组"][k]["蓝球"] for k in ("结果1", "结果2", "结果3", "结果4", "结果5", "结果6")}
    print(f"seed={seed}: 红球组合数={len(sets)}, 蓝球去重={len(bl)}")
    for rr, ks in sets.items():
        print(f"   {rr} → {ks}")

print("\n=== 2. 区块并列稳定性 ===")
for seed in (0, 42):
    eng = SelectionEngine(red_seq, blue_seq, rng=random.Random(seed), big_pool=18)
    out = eng.run()
    blocks = eng._enum_blocks(out["大底"], eng.forms())
    best_ov = blocks[0][1]
    tied = [c for c, ov in blocks if ov >= best_ov - 0.001]
    bp = sorted({x for c in tied for x in c})
    cover = len(set(out["大底"]) & set(bp))
    print(f"seed={seed}: 并列组合={len(tied)}, 并集={len(bp)}, 覆盖大底={cover}/18")

print("\n=== 3. 熵权权重分布（两种子） ===")
for seed in (0, 42):
    eng = SelectionEngine(red_seq, blue_seq, rng=random.Random(seed), big_pool=18)
    _, weights, _ = eng.score_red()
    top = sorted(enumerate(weights, 1), key=lambda x: x[1], reverse=True)
    top3 = [(i, round(w, 3)) for i, w in top[:3]]
    zeros = sum(1 for w in weights if w <= 1e-9)
    print(f"seed={seed}: TOP3={top3}, 权重≈0模块数={zeros}")

print("\n=== 4. 模块17峰度负值实测 ===")
r17 = mod17_kurtosis(red_seq, blue_seq)
neg = [v for v in r17 if v < 0]
print(f"负值个数={len(neg)}/33, 最小={min(r17):.3f}")

print("\n=== 5. FetchWorker假错误模拟（close后调用） ===")
tmp1 = os.path.join(tempfile.gettempdir(), "ssq_fw.db")
import shutil
shutil.copy2(DB, tmp1)
d = DrawDB(tmp1)
d.close()
try:
    d.latest_issue()
    print("✗ 未抛异常（与评估不符）")
except Exception as e:
    print(f"✓ 抛异常: {type(e).__name__}: {e}（界面将显示'同步失败'假错误）")
os.remove(tmp1)

print("\n=== 6. import_csv 缺列崩溃模拟 ===")
tmp2 = os.path.join(tempfile.gettempdir(), "ssq_ic.db")
shutil.copy2(DB, tmp2)
bad_csv = os.path.join(tempfile.gettempdir(), "bad_cols.csv")
with open(bad_csv, "w", encoding="utf-8-sig", newline="") as f:
    f.write("issue,date,red1,red2,red3,red4,red5,blue\n")  # 缺 red6
    f.write("9999001,2026-01-01,01,02,03,04,05,06\n")
d2 = DrawDB(tmp2)
try:
    n = d2.import_csv(bad_csv)
    print(f"✗ 未抛异常, 导入 {n} 条（与评估不符）")
except Exception as e:
    print(f"✓ 抛异常: {type(e).__name__}: {e}（界面无 try 包裹，将崩溃）")
d2.close()
os.remove(tmp2)
os.remove(bad_csv)

db.close()
print("\n第三轮综合验证完成")

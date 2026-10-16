# -*- coding: utf-8 -*-
"""对照评估核实探针：六组结果去重、区块并列、熵权权重、模块17负值、结果5排序。"""
import os
import sys
import random

sys.path.insert(0, r"E:\双色球智能选号\app")
from db import DrawDB
from engine import SelectionEngine, BLUE_MODULES

DB = r"E:\双色球智能选号\dist\data\ssq.db"
db = DrawDB(DB)
rows = db.get_latest_n(200)
red_seq = [r["reds"] for r in rows]
blue_seq = [r["blue"] for r in rows]

eng = SelectionEngine(red_seq, blue_seq, rng=random.Random(0), big_pool=18)
out = eng.run()
g = out["组"]

print("=== 1. 六组结果红球去重 ===")
reds_sets = {}
for k in ("结果1", "结果2", "结果3", "结果4", "结果5", "结果6"):
    rr = tuple(sorted(g[k]["红球"]))
    reds_sets.setdefault(rr, []).append(k)
    print(f"{k}: {rr}  蓝={g[k]['蓝球']}")
print(f"去重后红球组合数: {len(reds_sets)}")
for rr, ks in reds_sets.items():
    print(f"  组合 {rr} → {ks}")

print("\n=== 2. 区块轨道并列 ===")
rows_score, weights, total = eng.score_red()
blocks = eng._enum_blocks(out["大底"] if out["大底"] else None, eng.forms())
if blocks:
    best_ov = blocks[0][1]
    tied = [c for c, ov in blocks if ov >= best_ov - 0.001]
    bp = sorted({x for c in tied for x in c})
    print(f"最高重叠率: {best_ov}, 并列组合数: {len(tied)}, 并集大小: {len(bp)}")
    print(f"大底: {sorted(out['大底'])}")
    print(f"区块并集覆盖大底数: {len(set(out['大底']) & set(bp))}/{len(out['大底'])}")

print("\n=== 3. 熵权权重分布 ===")
top = sorted(enumerate(weights, 1), key=lambda x: x[1], reverse=True)
print("权重 TOP5:", [(i, round(w, 3)) for i, w in top[:5]])
print("权重 最小5:", [(i, round(w, 4)) for i, w in top[-5:]])

print("\n=== 4. 模块17（峰度）输出是否含负值 ===")
try:
    from engine import _kurtosis_score
    r17 = _kurtosis_score(red_seq)
    neg = [v for v in r17 if v < 0]
    print(f"峰度得分: 最小={min(r17):.3f} 最大={max(r17):.3f}, 负值个数={len(neg)}")
except Exception as e:
    print(f"取模块17失败: {e}")

print("\n=== 5. 结果5/6 排序键 ===")
print("结果5:", sorted(g["结果5"]["红球"]), " 结果6:", g["结果6"]["红球"])
print("结果1:", sorted(g["结果1"]["红球"]))
print("结果5==结果1? ", tuple(sorted(g["结果5"]["红球"])) == tuple(sorted(g["结果1"]["红球"])))
print("结果5==结果3? ", tuple(sorted(g["结果5"]["红球"])) == tuple(sorted(g["结果3"]["红球"])))

print("\n=== 6. 蓝球候选 ===")
comb, cand = eng.vote_blue()
print("蓝球候选 TOP3:", cand)

db.close()
print("\n探针完成")

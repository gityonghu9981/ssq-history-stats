# -*- coding: utf-8 -*-
"""V1.2.1 引擎回归：六组差异化、双层验证（注单蓝球必在对应候选集合内）、
包含关系、排除红/蓝生效。"""
import os
import sys
import random

sys.path.insert(0, r"E:\双色球智能选号\app")
from db import DrawDB
from engine import SelectionEngine

db = DrawDB(r"E:\双色球智能选号\dist\data\ssq.db")
rows = db.get_latest_n(200)
red_seq = [r["reds"] for r in rows]
blue_seq = [r["blue"] for r in rows]

all_ok = True
for seed in (0, 42):
    eng = SelectionEngine(red_seq, blue_seq, rng=random.Random(seed), big_pool=18)
    out = eng.run()
    g = out["组"]
    sets = {}
    blues = {}
    for k in ("结果1", "结果2", "结果3", "结果4", "结果5", "结果6"):
        rr = tuple(sorted(g[k]["红球"]))
        sets.setdefault(rr, []).append(k)
        bl = tuple(g[k]["蓝球"]) if isinstance(g[k]["蓝球"], list) else (g[k]["蓝球"],)
        blues.setdefault(bl, []).append(k)
    inc_ok = all(
        set(g[f"结果{k}"]["红球"]) <= set(g[f"结果{k+1}"]["红球"])
        for k in (1, 3, 5))
    rep_ok = (tuple(g["结果5"]["红球"]) != tuple(g["结果3"]["红球"])
              and tuple(g["结果6"]["红球"]) != tuple(g["结果2"]["红球"]))
    # 双层验证：注单蓝球（结果1/3/5）必须落在对应集合候选（结果2/4/6）内
    b_ok = (g["结果1"]["蓝球"] in g["结果2"]["蓝球"]
            and g["结果3"]["蓝球"] in g["结果4"]["蓝球"]
            and g["结果5"]["蓝球"] in g["结果6"]["蓝球"])
    print(f"seed={seed}: 红球组合数={len(sets)} 蓝球形态数={len(blues)} "
          f"包含={inc_ok} 复述检查={rep_ok} 双层验证蓝球={b_ok}")
    for rr, ks in sets.items():
        print(f"   红 {rr} -> {ks}")
    for bl, ks in blues.items():
        print(f"   蓝 {bl} -> {ks}")
    print(f"   注单蓝球: 结果1={g['结果1']['蓝球']} ∈ 结果2候选={g['结果2']['蓝球']} "
          f"| 结果3={g['结果3']['蓝球']} ∈ 结果4候选={g['结果4']['蓝球']} "
          f"| 结果5={g['结果5']['蓝球']} ∈ 结果6候选={g['结果6']['蓝球']}")
    all_ok = all_ok and inc_ok and rep_ok and b_ok and len(sets) >= 6

# 排除蓝球生效：排除 2，结果蓝球不应含 2
eng = SelectionEngine(red_seq, blue_seq, rng=random.Random(0),
                      big_pool=18, exclude_blue={2})
out = eng.run()
g = out["组"]
bad = []
for k in ("结果1", "结果2", "结果3", "结果4", "结果5", "结果6"):
    bl = g[k]["蓝球"]
    items = bl if isinstance(bl, list) else [bl]
    for x in items:
        if x == 2:
            bad.append(k)
ex_ok = not bad
print(f"排除蓝球2后，仍含2的结果: {bad if bad else '无（全部生效）'}")

# 排除红球验证
eng = SelectionEngine(red_seq, blue_seq, rng=random.Random(0),
                      big_pool=18, exclude_red={2, 4, 5})
out = eng.run()
g = out["组"]
bad2 = [k for k in ("结果1", "结果2", "结果3", "结果4", "结果5", "结果6")
        if {2, 4, 5} & set(g[k]["红球"])]
ex2_ok = not bad2
print(f"排除红球2/4/5后，仍含的结果: {bad2 if bad2 else '无（全部生效）'}")

db.close()
print(f"\nV1.2.1 引擎回归：{'全部通过 ✅' if all_ok and ex_ok and ex2_ok else '存在失败 ✗'}")

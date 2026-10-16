# -*- coding: utf-8 -*-
"""包含关系验证：结果2⊇1、4⊇3、6⊇5 + 排除号 + 结构。"""
import os, sys
sys.path.insert(0, r'E:\双色球智能选号\app')
from db import DrawDB
from engine import SelectionEngine
import random

db = DrawDB()
red = db.red_sequences()
blue = db.blue_sequences()
n = len(red)
window = 100

def check(t, excl_red=(), excl_blue=()):
    train_r = red[max(0, t - window):t]
    train_b = blue[max(0, t - window):t]
    rng = random.Random(t)
    eng = SelectionEngine(train_r, train_b, rng=rng, block_sample=1500,
                          exclude_red=list(excl_red), exclude_blue=list(excl_blue))
    out = eng.run()
    g = out["组"]
    r1, r2 = set(g["结果1"]["红球"]), set(g["结果2"]["红球"])
    r3, r4 = set(g["结果3"]["红球"]), set(g["结果4"]["红球"])
    r5, r6 = set(g["结果5"]["红球"]), set(g["结果6"]["红球"])
    assert len(r1) == 6 and len(r3) == 6 and len(r5) == 6, f"注单非6码: t={t}"
    assert len(r2) >= 6 and len(r4) >= 6 and len(r6) >= 6, f"集合不足6码: t={t}"
    assert r1 <= r2, f"结果2不包含结果1: t={t}\n 1={sorted(r1)}\n 2={sorted(r2)}"
    assert r3 <= r4, f"结果4不包含结果3: t={t}\n 3={sorted(r3)}\n 4={sorted(r4)}"
    assert r5 <= r6, f"结果6不包含结果5: t={t}\n 5={sorted(r5)}\n 6={sorted(r6)}"
    for ex in excl_red:
        for key in g.values():
            assert ex not in key["红球"], f"排除号{ex}出现在{key}: t={t}"
    for ex in excl_blue:
        for key in g.values():
            assert key["蓝球"] != ex, f"排除蓝{ex}出现: t={t}"
    return out

# 1) 多期抽查（含早期/中期/近期）
ts = [500, 1000, 1500, 2000, 2500, 3000, 3185, 3400, 3490, 3509]
for t in ts:
    check(t)
    print(f"✓ t={t} 包含关系全部成立")

# 2) 随机 20 期
for _ in range(20):
    t = random.Random().randint(window, n - 1)
    check(t)
print("✓ 随机 20 期包含关系全部成立")

# 3) 排除号场景
for t in ts:
    check(t, excl_red=[2, 5, 9], excl_blue=[4])
print("✓ 排除号场景全部生效")

# 4) 排除过多号（红球排除 20 个）
check(3400, excl_red=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20])
print("✓ 排除20红 场景通过")

print("\n全部包含关系验证通过 ✅")
db.close()

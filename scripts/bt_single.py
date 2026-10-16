# -*- coding: utf-8 -*-
"""单测 T3185：窗口数据合法性 + 逐模块定位。"""
from db import DrawDB
from engine import SelectionEngine, _morph_stats
import engine as E
import random, sys

db = DrawDB()
red = db.red_sequences()
blue = db.blue_sequences()
t = 3185
window = 100
train_r = red[max(0, t - window):t]
train_b = blue[max(0, t - window):t]

# 1. 窗口数据合法性
print(f"窗口长度: {len(train_r)}")
bad = 0
for i, seq in enumerate(train_r):
    if len(seq) != 6 or len(set(seq)) != 6 or not all(1 <= x <= 33 for x in seq):
        print(f"  异常期 {i}: {seq}")
        bad += 1
print(f"数据异常期数: {bad}")

# 2. 逐 A 模块跑
print("逐模块运行:")
for name, fn in E.A_MODULES:
    try:
        out = fn(train_r, train_b)
        assert len(out) == 33
    except Exception as e:
        print(f"  ✗ {name}: {type(e).__name__} {e}")
print("A类全部完成")

# 3. _morph_stats（B 类基础）
try:
    st = _morph_stats(train_r)
    print("_morph_stats OK, 键数:", len(st))
    for k, v in st.items():
        print(f"  {k}: 取值数 {len(v)}")
except Exception as e:
    print(f"_morph_stats 异常: {type(e).__name__} {e}")

# 4. 逐 B 模块跑
for name, fn in E.B_MODULES:
    try:
        out = fn(train_r, train_b)
    except Exception as e:
        print(f"  ✗ {name}: {type(e).__name__} {e}")
print("B类全部完成")

# 5. 完整 run
eng = SelectionEngine(train_r, train_b, rng=random.Random(t), block_sample=1500)
out = eng.run()
print("run 完成, 大底:", out["大底"])
db.close()
print("单测 T3185 全部通过")

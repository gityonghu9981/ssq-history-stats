# -*- coding: utf-8 -*-
"""逐期追踪块 2200-2350，定位数据触发的崩溃期。"""
from db import DrawDB
from engine import SelectionEngine
import random, sys

db = DrawDB()
red = db.red_sequences()
blue = db.blue_sequences()
window = 100
for t in range(2200, 2350):
    print(f"T{t}", flush=True)
    train_r = red[max(0, t - window):t]
    train_b = blue[max(0, t - window):t]
    rng = random.Random(t)
    eng = SelectionEngine(train_r, train_b, rng=rng, block_sample=1500)
    out = eng.run()
print("块 2200-2350 全部完成")
db.close()

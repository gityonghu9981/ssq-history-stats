# -*- coding: utf-8 -*-
"""用 dist 显式 db 逐期追踪块 2200-2350，对比默认 db 是否差异。"""
from db import DrawDB
from engine import SelectionEngine
import random, sys

db = DrawDB(r"E:\双色球智能选号\dist\data\ssq.db")
red = db.red_sequences()
blue = db.blue_sequences()
print("dist db 期数:", len(red))
window = 100
for t in range(2200, 2350):
    print(f"T{t}", flush=True)
    train_r = red[max(0, t - window):t]
    train_b = blue[max(0, t - window):t]
    rng = random.Random(t)
    eng = SelectionEngine(train_r, train_b, rng=rng, block_sample=1500)
    out = eng.run()
print("dist db 块 2200-2350 全部完成")
db.close()

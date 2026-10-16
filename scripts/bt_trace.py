# -*- coding: utf-8 -*-
"""逐期追踪：回测 500 期，每期打印 t，定位崩溃期。"""
from db import DrawDB
from engine import SelectionEngine
import random

db = DrawDB()
red = db.red_sequences()
blue = db.blue_sequences()
n = len(red)
window = 100
rounds = 500
begin = n - rounds
for t in range(begin, n):
    print(f"T{t}", flush=True)
    train_r = red[max(0, t - window):t]
    train_b = blue[max(0, t - window):t]
    rng = random.Random(t)
    eng = SelectionEngine(train_r, train_b, rng=rng, block_sample=1500)
    out = eng.run()
    assert not out["无数据"]
print("500期全部完成")
db.close()

# -*- coding: utf-8 -*-
"""排除号功能验证。"""
import os, sys
sys.path.insert(0, r'E:\双色球智能选号\app')
from db import DrawDB
from engine import SelectionEngine
import random

db = DrawDB()
red = db.red_sequences()
blue = db.blue_sequences()
eng = SelectionEngine(red, blue, rng=random.Random(1),
                      exclude_red={1, 2, 3, 33}, exclude_blue={16})
out = eng.run()
for k in range(1, 7):
    g = out["组"][f"结果{k}"]
    assert not (set(g["红球"]) & {1, 2, 3, 33}), f"结果{k} 含排除红球 {g}"
    assert g["蓝球"] != 16, f"结果{k} 含排除蓝球"
print("排除号验证通过：6组结果均不含 01,02,03,33 与蓝球16")
print("大底:", sorted(out["大底"]))
db.close()

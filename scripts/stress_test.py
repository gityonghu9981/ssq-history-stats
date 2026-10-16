# -*- coding: utf-8 -*-
"""崩溃对照实验：定位 40-60 秒必崩的真正来源。
A: 纯 sleep 90s（时长）  B: 300万次 random.sample（抽样计算）
C: 引擎300期 block_sample=0（无抽样枚举）  D: 引擎300期原样（对照，预期崩）
用法: python stress_test.py A|B|C|D
"""
import random
import sys
import time

MODE = sys.argv[1] if len(sys.argv) > 1 else "A"

if MODE == "A":
    time.sleep(90)
    print("A 完成: 纯 sleep 90s 未崩")

elif MODE == "B":
    rng = random.Random(7)
    pool = list(range(1, 34))
    t0 = time.time()
    for _ in range(3_000_000):
        rng.sample(pool, 6)
    print(f"B 完成: 300万次 sample, 耗时 {time.time()-t0:.0f}s 未崩")

elif MODE in ("C", "D", "C4", "D2"):
    from db import DrawDB
    from engine import SelectionEngine
    db = DrawDB()
    red = db.red_sequences()
    blue = db.blue_sequences()
    n = len(red)
    window = 100
    rounds = 300 if MODE in ("C", "D") else 400
    begin = n - rounds
    sample = 0 if MODE in ("C", "C4") else 1500
    t0 = time.time()
    for t in range(begin, n):
        train_r = red[max(0, t - window):t]
        train_b = blue[max(0, t - window):t]
        rng = random.Random(t)
        eng = SelectionEngine(train_r, train_b, rng=rng, block_sample=sample)
        out = eng.run()
    print(f"{MODE} 完成: 引擎{rounds}期 sample={sample}, 耗时 {time.time()-t0:.0f}s 未崩")
    db.close()

else:
    print("用法: stress_test.py A|B|C|D")

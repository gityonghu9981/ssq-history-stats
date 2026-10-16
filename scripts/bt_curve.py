# -*- coding: utf-8 -*-
"""崩溃率-期数曲线：同一引擎按不同回测期数各跑 2 次。"""
import sys, time
from db import DrawDB
from backtest import Backtest

db = DrawDB()
red = db.red_sequences()
blue = db.blue_sequences()
rounds = int(sys.argv[1])
t0 = time.time()
bt = Backtest(red, blue, window=100, max_rounds=rounds, block_sample=1500)
res = bt.run()
dt = time.time() - t0
print(f"OK {rounds}期 耗时{dt:.0f}s 大底{res['大底平均命中']:.3f}")
db.close()

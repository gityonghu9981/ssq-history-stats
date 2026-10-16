# -*- coding: utf-8 -*-
"""定位 check_forms 类型错误的最小复现。"""
import os, sys
sys.path.insert(0, r'E:\双色球智能选号\app')
from data_fetch import fetch_page
from db import DrawDB
from engine import SelectionEngine
from backtest import Backtest
import traceback

rows = fetch_page(150)
db = DrawDB(":memory:")
db.insert_many(rows)
seqs_r = db.red_sequences()
seqs_b = db.blue_sequences()

bt = Backtest(seqs_r, seqs_b, window=80, max_rounds=30)
n = len(seqs_r)
begin = n - min(30, n - 80)

for t in range(begin, n):
    train_r = seqs_r[max(0, t - 80):t]
    train_b = seqs_b[max(0, t - 80):t]
    eng = SelectionEngine(train_r, train_b, rng=None)
    try:
        out = eng.run()
    except Exception:
        print(f"t={t} 出错")
        # 手动复现
        _, _, total = eng.score_red()
        forms = eng.forms()
        order = sorted(range(33), key=lambda i: total[i], reverse=True)
        pool = [i + 1 for i in order[:18]]
        print("pool 类型:", type(pool[0]), pool[:5])
        print("total 元素类型:", type(total[0]), total[:3])
        from engine import check_forms
        import random
        combo = tuple(sorted(random.Random(t).sample(pool, 6)))
        print("combo 类型:", [type(x).__name__ for x in combo])
        ok, bad = check_forms(combo, forms)
        print("ok:", ok, "bad:", bad)
        traceback.print_exc()
        break

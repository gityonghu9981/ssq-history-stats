# -*- coding: utf-8 -*-
"""完全复刻冒烟测试的回测参数，复现 TypeError 并打印现场。"""
import os, sys
sys.path.insert(0, r'E:\双色球智能选号\app')
import random
from data_fetch import fetch_page
from db import DrawDB
from engine import SelectionEngine, check_forms

rows = fetch_page(150)
db = DrawDB(":memory:")
db.insert_many(rows)
seqs_r = db.red_sequences()
seqs_b = db.blue_sequences()

n = len(seqs_r)
window = 80
max_rounds = 30
begin = n - min(max_rounds, n - window)

for t in range(begin, n):
    train_r = seqs_r[max(0, t - window):t]
    train_b = seqs_b[max(0, t - window):t]
    rng = random.Random(t)
    eng = SelectionEngine(train_r, train_b, rng=rng)
    _, _, total = eng.score_red()
    forms = eng.forms()
    order = sorted(range(33), key=lambda i: total[i], reverse=True)
    pool = [i + 1 for i in order[:18]]
    for attempt in range(50):
        combo = tuple(sorted(rng.sample(pool, 6)))
        try:
            check_forms(combo, forms)
        except TypeError as e:
            print("=" * 60)
            print(f"t={t} attempt={attempt} 触发 TypeError: {e}")
            print("pool 类型元素:", [type(x).__name__ for x in pool[:6]])
            print("pool 内容:", pool)
            print("combo:", combo)
            print("combo 元素类型:", [type(x).__name__ for x in combo])
            print("forms 键:", list(forms.keys()))
            print("四区比 val:", forms.get("四区比"))
            raise SystemExit(1)
print("未复现，50次采样均正常")

# -*- coding: utf-8 -*-
"""冒烟测试：拉取少量真实数据，验证引擎与回测可运行。"""
import os, sys
sys.path.insert(0, r'E:\双色球智能选号\app')
import sys
from data_fetch import fetch_page
from db import DrawDB
from engine import SelectionEngine
from backtest import Backtest


def main():
    print("1) 拉取最近 150 期真实数据 ...")
    rows = fetch_page(150)
    print(f"   拉到 {len(rows)} 期，最新 {rows[0]['issue']}，最早 {rows[-1]['issue']}")

    db = DrawDB(":memory:")
    db.insert_many(rows)
    seqs_r = db.red_sequences()
    seqs_b = db.blue_sequences()
    print(f"   红球序列 {len(seqs_r)} 期，蓝球序列 {len(seqs_b)} 期")

    print("2) 运行选号引擎 ...")
    eng = SelectionEngine(seqs_r, seqs_b, rng=None)
    out = eng.run()
    assert not out["无数据"]
    assert len(out["大底"]) == 18
    for k in range(1, 7):
        g = out["组"][f"结果{k}"]
        assert len(g["红球"]) == 6 and 1 <= g["蓝球"] <= 16, f"{k} 不合法"
        assert all(1 <= x <= 33 for x in g["红球"])
    print(f"   6 组结果合法。大底: {sorted(out['大底'])}")
    print(f"   形态模块: {list(out['形态'].keys())}")
    print(f"   蓝球候选: {out['蓝球候选']}")
    print("   结果1:", out["组"]["结果1"]["红球"], "蓝", out["组"]["结果1"]["蓝球"])
    print("   结果2:", out["组"]["结果2"]["红球"], "蓝", out["组"]["结果2"]["蓝球"])

    print("3) 运行滚动回测（窗口80，回测30期）...")
    bt = Backtest(seqs_r, seqs_b, window=80, max_rounds=30)
    res = bt.run()
    print(f"   回测 {res['回测期数']} 期")
    print(f"   大底平均命中: {res['大底平均命中']:.3f}（随机基准 {res['随机基准红球']}）")
    r1 = res["结果1"]
    if r1:
        print(f"   结果1 平均红球命中: {r1['平均红球命中']:.3f}，蓝球命中率 {r1['蓝球命中率']*100:.1f}%（随机 {res['随机基准蓝球']}%）")
        print(f"   结果1 奖级分布: {r1['奖级分布']}")
    print("冒烟测试通过 ✅")


if __name__ == "__main__":
    main()

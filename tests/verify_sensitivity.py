# -*- coding: utf-8 -*-
"""数据敏感性逐层测试：删除 0/1/5/20 期，观察投票、评分排序、大底、6组的变化。
只读测试，不改任何代码与数据（用临时库副本）。"""
import os
import shutil
import sys
import tempfile
import random

sys.path.insert(0, r"E:\双色球智能选号\app")
from db import DrawDB
from engine import SelectionEngine

SRC = r"E:\双色球智能选号\dist\data\ssq.db"
tmp = os.path.join(tempfile.gettempdir(), "ssq_sens.db")
shutil.copy2(SRC, tmp)

def state(db):
    """返回引擎各层状态（与 UI 相同的调用方式）。"""
    rows = db.get_latest_n(200)
    red_seq = [r["reds"] for r in rows]
    blue_seq = [r["blue"] for r in rows]
    eng = SelectionEngine(red_seq, blue_seq, rng=random.Random(0), big_pool=18)
    out = eng.run()
    # 投票层
    votes = [0] * 33
    rows_score, weights, total = eng.score_red()
    for row in rows_score:
        order = sorted(range(33), key=lambda i: row[i], reverse=True)[:18]
        for i in order:
            votes[i] += 1
    top6 = sorted(range(33), key=lambda i: votes[i] + total[i] / max(total))[:6]
    top10 = sorted(range(33), key=lambda i: votes[i] + total[i] / max(total))[:10]
    g = out["组"]
    return {
        "投票数组": tuple(votes),
        "评分TOP6": tuple(x + 1 for x in top6),
        "评分TOP10": tuple(x + 1 for x in top10),
        "大底": tuple(sorted(out["大底"])),
        "结果1": (tuple(g["结果1"]["红球"]), g["结果1"]["蓝球"]),
        "结果2": (tuple(g["结果2"]["红球"]), g["结果2"]["蓝球"]),
        "结果3": (tuple(g["结果3"]["红球"]), g["结果3"]["蓝球"]),
        "结果4": (tuple(g["结果4"]["红球"]), g["结果4"]["蓝球"]),
        "结果5": (tuple(g["结果5"]["红球"]), g["结果5"]["蓝球"]),
        "结果6": (tuple(g["结果6"]["红球"]), g["结果6"]["蓝球"]),
    }

db = DrawDB(tmp)
base = state(db)
print("基线（未删）:")
print("  评分TOP6:", list(base["评分TOP6"]))
print("  大底:", list(base["大底"]))
print("  结果1:", list(base["结果1"][0]), "蓝", base["结果1"][1])
print("  结果2:", list(base["结果2"][0]))

issues = [r["issue"] for r in db.get_all("asc")]
for k, n_del in (("删1期", 1), ("删5期", 5), ("删20期", 20)):
    d2 = DrawDB(tmp)
    del_issues = issues[-n_del:]
    for iss in del_issues:
        d2._conn.execute("DELETE FROM ssq_draws WHERE issue=?", (iss,))
    d2._conn.commit()
    s = state(d2)
    diffs = [key for key in base if base[key] != s[key]]
    print(f"\n{n_del}期: 删除 {del_issues[-1]}…共{n_del}期")
    print(f"  变化层: {diffs if diffs else '无（全部相同）'}")
    if "结果1" in diffs:
        print(f"  结果1: {list(s['结果1'][0])} 蓝 {s['结果1'][1]}")
    d2.close()

db.close()
os.remove(tmp)
print("\n敏感性逐层测试完成")

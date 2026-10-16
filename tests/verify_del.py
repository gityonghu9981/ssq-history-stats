# -*- coding: utf-8 -*-
"""验证：删除历史数据对测算结果的影响（临时库副本）。
场景A：删最近 200 期窗口内的数据 → 预期结果变化
场景B：删最近 200 期窗口外的旧数据 → 预期结果不变（引擎只取最近 200 期）
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, r"E:\双色球智能选号\app")
from db import DrawDB
from engine import SelectionEngine
import random

SRC = r"E:\双色球智能选号\dist\data\ssq.db"
tmp = os.path.join(tempfile.gettempdir(), "ssq_del_test.db")
shutil.copy2(SRC, tmp)
db = DrawDB(tmp)
n0 = db.count()
print(f"临时库期数: {n0}")

def run_engine(d):
    rows = d.get_latest_n(200)
    red_seq = [r["reds"] for r in rows]
    blue_seq = [r["blue"] for r in rows]
    rng = random.Random(42)
    eng = SelectionEngine(red_seq, blue_seq, rng=rng, block_sample=1500)
    out = eng.run()
    g = out["组"]
    return {
        "大底": out["大底"],
        "结果1": (g["结果1"]["红球"], g["结果1"]["蓝球"]),
        "结果2": (g["结果2"]["红球"], g["结果2"]["蓝球"]),
        "结果3": (g["结果3"]["红球"], g["结果3"]["蓝球"]),
        "结果4": (g["结果4"]["红球"], g["结果4"]["蓝球"]),
        "结果5": (g["结果5"]["红球"], g["结果5"]["蓝球"]),
        "结果6": (g["结果6"]["红球"], g["结果6"]["蓝球"]),
    }

base = run_engine(db)
print("基线结果1:", base["结果1"])
print("基线大底:", base["大底"])

# 场景A：删除最近 5 期（200 窗口内）
db2 = DrawDB(tmp)
rows = db2.get_all("asc")
issues_all = [r["issue"] for r in rows]
recent5 = issues_all[-5:]
for iss in recent5:
    db2._conn.execute("DELETE FROM ssq_draws WHERE issue=?", (iss,))
db2._conn.commit()
print(f"\n场景A：删除最近5期 {recent5}")
a = run_engine(db2)
same_a = a == base
print("删除后结果1:", a["结果1"])
print(f"与基线{'完全一致' if same_a else '已变化'}")

# 场景B：恢复后删除最早 10 期（200 窗口外）
db2._conn.execute("DELETE FROM ssq_draws WHERE issue IN (SELECT issue FROM ssq_draws ORDER BY issue ASC LIMIT 10)")
db2._conn.commit()
b = run_engine(db2)
same_b = b == base
print(f"\n场景B：再删除最早10期（200窗口外）")
print("删除后结果1:", b["结果1"])
print(f"与基线{'完全一致' if same_b else '已变化'}")

print("\n结论:")
print(f"场景A(删窗口内): {'结果变化 ✅ 数据删除确实影响测算' if not same_a else '结果不变 ✗ 存在异常'}")
print(f"场景B(删窗口外): {'结果不变（符合设计：引擎只取最近200期）' if same_b else '结果变化（窗口前移）'}")
db.close()
os.remove(tmp)

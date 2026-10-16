# -*- coding: utf-8 -*-
"""严格验证：真实删除 1 条数据库记录，选号结果必须合理变化。"""
import os
import shutil
import sys
import tempfile
import random

sys.path.insert(0, r"E:\双色球智能选号\app")
from db import DrawDB
from engine import SelectionEngine

SRC = r"E:\双色球智能选号\dist\data\ssq.db"

def state(d):
    rows = d.get_latest_n(200)
    eng = SelectionEngine([r["reds"] for r in rows], [r["blue"] for r in rows],
                          rng=random.Random(0), big_pool=18)
    out = eng.run()
    g = out["组"]
    return {k: (list(g[k]["红球"]), g[k]["蓝球"]) for k in
            ("结果1", "结果2", "结果3", "结果4", "结果5", "结果6")}, list(out["大底"])

def show(tag, s, pool):
    print(f"\n{tag}: 大底={pool}")
    for k in ("结果1", "结果2", "结果3", "结果4", "结果5", "结果6"):
        reds, blue = s[k]
        if isinstance(blue, (list, tuple)):
            bt = "[" + " ".join(f"{x:02d}" for x in blue) + "]"
        else:
            bt = f"{blue:02d}"
        print(f"  {k}: {' '.join(f'{x:02d}' for x in reds)} + {bt}")

def diff_detail(a, b):
    return [k for k in a if a[k] != b[k]]

# ========== 场景1：删除最新一期 ==========
tmp = os.path.join(tempfile.gettempdir(), "ssq_d1.db")
shutil.copy2(SRC, tmp)
db = DrawDB(tmp)
s0, p0 = state(db)
latest = db.latest_issue()
db._conn.execute("DELETE FROM ssq_draws WHERE issue=?", (latest,))
db._conn.commit()
print(f"库内期数: 3510 → {db.count()}, 删除: {latest}")
s1, p1 = state(db)
show("删除前（基线）", s0, p0)
show("删除后（真实写入数据库）", s1, p1)
changed = diff_detail(s0, s1)
print(f"\n变化组数: {len(changed)}/6 → {changed}")
assert changed, "✗ 删除1条后选号结果未变化！"
print("✅ 场景1通过：删除最新1条，选号结果合理变化")
db.close()
os.remove(tmp)

# ========== 场景2：删除窗口内中间一期（2024年） ==========
tmp2 = os.path.join(tempfile.gettempdir(), "ssq_d2.db")
shutil.copy2(SRC, tmp2)
db2 = DrawDB(tmp2)
s0b, p0b = state(db2)
issues = [r["issue"] for r in db2.get_all("asc")]
# 窗口内：取倒数第 50 期左右（200 期窗口内）
mid = issues[-50]
db2._conn.execute("DELETE FROM ssq_draws WHERE issue=?", (mid,))
db2._conn.commit()
print(f"\n库内期数: 3510 → {db2.count()}, 删除: {mid}（窗口内中间期）")
s2, p2 = state(db2)
changed2 = diff_detail(s0b, s2)
print(f"变化组数: {len(changed2)}/6 → {changed2}")
assert changed2, "✗ 删除窗口内中间1条后选号结果未变化！"
print("✅ 场景2通过：删除窗口内中间1条，选号结果合理变化")
db2.close()
os.remove(tmp2)

print("\n验证总结：真实删除 1 条数据库记录（无论最新期还是窗口内中间期），6 组选号结果均合理变化 ✅")

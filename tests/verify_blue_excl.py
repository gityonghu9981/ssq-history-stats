# -*- coding: utf-8 -*-
"""蓝球排除兜底对称性专项：候选全被排除时从全范围按综合分取非排除号，
与红球侧兜底对齐；仅 16 号全被排除时才退回原始候选。"""
import os
import sys
import random

sys.path.insert(0, r"E:\双色球智能选号\app")
from db import DrawDB
from engine import SelectionEngine

db = DrawDB(r"E:\双色球智能选号\dist\data\ssq.db")
rows = db.get_latest_n(200)
red_seq = [r["reds"] for r in rows]
blue_seq = [r["blue"] for r in rows]
db.close()

def run_with(excl):
    eng = SelectionEngine(red_seq, blue_seq, rng=random.Random(0),
                          big_pool=18, exclude_blue=set(excl))
    g = eng.run()["组"]
    return g

ok = True

# 场景1：号码轨道候选 [2,4,5] 全被排除 → 从全范围取非排除综合分 TOP3
g = run_with([2, 4, 5])
b2 = g["结果2"]["蓝球"]
b1 = g["结果1"]["蓝球"]
s1 = (not ({2, 4, 5} & set(b2)) and len(b2) == 3
      and b1 in b2 and b1 not in (2, 4, 5))
print(f"场景1 排除[2,4,5]: 结果2候选={b2} 结果1蓝球={b1} "
      f"{'✅' if s1 else '✗'}")
ok = ok and s1

# 场景2：区块轨道候选 [1,2,3] 全被排除 → 从全范围取非排除综合分 TOP3
g = run_with([1, 2, 3])
b4 = g["结果4"]["蓝球"]
b3 = g["结果3"]["蓝球"]
s2 = (not ({1, 2, 3} & set(b4)) and len(b4) == 3
      and b3 in b4 and b3 not in (1, 2, 3))
print(f"场景2 排除[1,2,3]: 结果4候选={b4} 结果3蓝球={b3} "
      f"{'✅' if s2 else '✗'}")
ok = ok and s2

# 场景3：排除一部分（非全排除）→ 正常过滤
g = run_with([2])
b2b = g["结果2"]["蓝球"]
s3 = (2 not in b2b and len(b2b) == 2)
print(f"场景3 排除[2]: 结果2候选={b2b} {'✅' if s3 else '✗'}")
ok = ok and s3

# 场景4：16 个蓝球全被排除 → 最后兜底退回原始候选（与红球侧最后兜底一致）
g = run_with(range(1, 17))
b1z = g["结果1"]["蓝球"]
b3z = g["结果3"]["蓝球"]
s4 = (b1z in (1, 2, 3, 4, 5) and b3z in (1, 2, 3))
print(f"场景4 全排除: 结果1蓝球={b1z} 结果3蓝球={b3z} "
      f"{'✅' if s4 else '✗'}")
ok = ok and s4

# 场景5：双层验证在排除场景仍成立
g = run_with([2, 4, 5])
s5 = (g["结果1"]["蓝球"] in g["结果2"]["蓝球"]
      and g["结果3"]["蓝球"] in g["结果4"]["蓝球"]
      and g["结果5"]["蓝球"] in g["结果6"]["蓝球"])
print(f"场景5 双层验证（排除场景）: {'✅' if s5 else '✗'}")
ok = ok and s5

print(f"\n蓝球排除兜底专项：{'全部通过 ✅' if ok else '存在失败 ✗'}")

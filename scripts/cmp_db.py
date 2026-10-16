# -*- coding: utf-8 -*-
"""对比默认库与 dist 库的数据差异。"""
from db import DrawDB

paths = {
    "默认库": r"E:\双色球智能选号\data\ssq.db",
    "dist库": r"E:\双色球智能选号\dist\data\ssq.db",
}
dbs = {}
for name, p in paths.items():
    import os
    print(f"{name}: 存在={os.path.exists(p)} 大小={os.path.getsize(p) if os.path.exists(p) else 0}")
    d = DrawDB(p)
    dbs[name] = d
    reds = d.red_sequences()
    blues = d.blue_sequences()
    rows = d.get_all("asc")
    print(f"  期数={len(reds)} 首期={rows[0]['issue']} 末期={rows[-1]['issue']}")

a = dbs["默认库"].get_all("asc")
b = dbs["dist库"].get_all("asc")
print(f"\n期数: 默认={len(a)} dist={len(b)}")

# 按期号对齐对比
amap = {r["issue"]: r for r in a}
bmap = {r["issue"]: r for r in b}
issues_a = set(amap)
issues_b = set(bmap)
print(f"默认独有期数: {len(issues_a - issues_b)} (示例 {sorted(issues_a - issues_b)[:5]})")
print(f"dist独有期数: {len(issues_b - issues_a)} (示例 {sorted(issues_b - issues_a)[:5]})")

common = sorted(issues_a & issues_b)
diff_count = 0
for iss in common:
    ra = amap[iss]
    rb = bmap[iss]
    if ra["reds"] != rb["reds"] or ra["blue"] != rb["blue"]:
        diff_count += 1
        if diff_count <= 5:
            print(f"  号码不同 {iss}: 默认={ra['reds']}+{ra['blue']} dist={rb['reds']}+{rb['blue']}")
print(f"相同期号中号码不同的期数: {diff_count}")

# 检查 dist 库索引 2177-2277 附近数据合法性
print("\ndist 库索引 2170-2280 期数据检查:")
brows = b
for i in range(2170, min(2280, len(brows))):
    r = brows[i]
    reds = r["reds"]
    ok = (len(reds) == 6 and len(set(reds)) == 6 and
          all(isinstance(x, int) and 1 <= x <= 33 for x in reds))
    if not ok:
        print(f"  ✗ 索引{i} {r['issue']}: {reds}+{r['blue']}")
print("dist 索引 2170-2280 检查完成")

for d in dbs.values():
    d.close()

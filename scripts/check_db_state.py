# -*- coding: utf-8 -*-
"""检查正式库当前状态：期数、最新期、首期，判断是否真的删除过。"""
import sys
sys.path.insert(0, r"E:\双色球智能选号\app")
from db import DrawDB

for name, path in (
    ("程序数据", r"E:\双色球智能选号\dist\双色球智能选号\data\ssq.db"),
    ("打包源数据", r"E:\双色球智能选号\dist\data\ssq.db"),
    ("默认数据", r"E:\双色球智能选号\data\ssq.db"),
):
    import os
    if not os.path.exists(path):
        print(f"{name}: 不存在 {path}")
        continue
    d = DrawDB(path)
    rows = d.get_all("asc")
    print(f"{name}: {len(rows)} 期, 首期={rows[0]['issue']}, 末期={rows[-1]['issue']}")
    # 最近 10 期
    recent = [r["issue"] for r in rows[-10:]]
    print(f"  最近10期: {recent}")
    d.close()

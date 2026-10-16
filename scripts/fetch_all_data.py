# -*- coding: utf-8 -*-
"""
全量拉取双色球历史开奖记录并写入本地 SQLite。
数据源：中彩网（中国福利彩票发行管理中心直属网站）往期回顾，
覆盖 2003 年首期至今全部开奖记录。
用法：python fetch_all_data.py
"""
import os, sys
sys.path.insert(0, r'E:\双色球智能选号\app')
import sys
import time
from db import DrawDB
from data_fetch import fetch_zhcw_all, fetch_all


def main():
    db = DrawDB()
    existing = db.count()
    print(f"本地现有数据：{existing} 期，最新期 {db.latest_issue()}")

    already = set()
    if existing:
        for d in db.get_all():
            already.add(d["issue"])

    t0 = time.time()
    print("开始从中彩网拉取全量历史（2003 年至今）…")
    rows = fetch_zhcw_all(
        already_issues=already,
        progress_cb=lambda n, issue: print(f"  已拉取 {n} 期，最新到 {issue}"),
    )
    if not rows:
        print("没有拉到新数据。")
        return

    db.insert_many(rows)
    total = db.count()
    print(f"本次新增 {len(rows)} 期，库内共 {total} 期")
    print(f"最早期号：{db.first_issue()}，最新期号：{db.latest_issue()}")
    print(f"数据文件：{db.db_path}")
    print(f"耗时：{time.time() - t0:.1f} 秒")

    # 交叉校验：若库内缺少 2013 年至今，用福彩官网接口补充字段（销售额/奖池）
    if total and db.latest_issue():
        try:
            from data_fetch import fetch_all as fetch_cwl
            cwl = fetch_cwl(already_issues=already | {d["issue"] for d in rows})
            if cwl:
                db.insert_many(cwl)
                print(f"福彩官网补充 {len(cwl)} 期（含销售额/奖池字段），库内共 {db.count()} 期")
        except Exception as e:
            print(f"福彩官网补充跳过：{e}")


if __name__ == "__main__":
    main()

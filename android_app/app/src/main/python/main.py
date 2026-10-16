# -*- coding: utf-8 -*-
"""Android 版入口：Chaquopy 从 Java 调用。
功能：选号（六组双轨）、限量回测、历史数据查询、粘贴导入。
全部本地运行，不依赖网络。"""
import json
import random

from auth import verify_activate
import backtest
import db as dbmod
import engine as engmod

_DB_PATH = None


def init(db_path):
    global _DB_PATH
    _DB_PATH = db_path


def _load_all():
    """取全量历史（从最早一期到现在）作建模窗口。"""
    d = dbmod.DrawDB(_DB_PATH)
    rows = d.get_all()
    d.close()
    return [r["reds"] for r in rows], [r["blue"] for r in rows]


def _parse_nums(s):
    """解析逗号分隔号码串（空串 → 空集合）。"""
    out = set()
    for p in str(s or "").replace("，", ",").replace(" ", ",").split(","):
        p = p.strip()
        if p.isdigit():
            out.add(int(p))
    return out


def pick(exclude_red="", exclude_blue=""):
    """选号：全量历史建模（最早一期到现在），返回六组结果 + 大底 + 蓝球候选（JSON 字符串）。"""
    red, blue = _load_all()
    eng = engmod.SelectionEngine(
        red, blue, rng=random.Random(), big_pool=18,
        exclude_red=_parse_nums(exclude_red),
        exclude_blue=_parse_nums(exclude_blue))
    out = eng.run()
    groups = {}
    for k, v in out["组"].items():
        groups[k] = {"红球": v["红球"], "蓝球": v["蓝球"], "来源": v["来源"]}
    return json.dumps({
        "训练期数": len(red),
        "大底": out["大底"],
        "蓝球候选": out["蓝球候选"],
        "组": groups,
    }, ensure_ascii=False)


def backtest_limited(max_rounds=500, window=100):
    """限量回测（Android 单进程，避免过久）：返回简化视图 JSON。"""
    d = dbmod.DrawDB(_DB_PATH)
    all_rows = d.get_all()
    d.close()
    red = [r["reds"] for r in all_rows]
    blue = [r["blue"] for r in all_rows]
    bt = backtest.Backtest(red, blue, window=window, use_seed=True,
                           max_rounds=max_rounds, block_sample=1500)
    res = bt.run()
    view = {
        "回测期数": res["回测期数"],
        "大底平均命中": round(res["大底平均命中"], 3),
        "随机基准红球": res["随机基准红球"],
        "随机基准蓝球": res["随机基准蓝球"],
    }
    for k in ("结果1", "结果2", "结果3", "结果4", "结果5", "结果6"):
        s = res[k]
        if s:
            view[k] = {
                "平均红球命中": round(s["平均红球命中"], 3),
                "蓝球命中率": round(s["蓝球命中率"] * 100, 2),
                "蓝球候选码数": s.get("蓝球候选码数", 1),
                "奖级分布": dict(s.get("奖级分布", {})),
            }
    return json.dumps(view, ensure_ascii=False, indent=2)


def get_stats():
    """数据统计：总期数、首期、最新期。"""
    d = dbmod.DrawDB(_DB_PATH)
    n = len(d.get_all())
    first = d.first_issue()
    last = d.latest_issue()
    d.close()
    return json.dumps({"总期数": n, "首期": first, "最新期": last},
                      ensure_ascii=False, indent=2)


def get_history(n=20):
    """最近 n 期开奖记录（升序）：期号/日期/红球/蓝球。"""
    d = dbmod.DrawDB(_DB_PATH)
    rows = d.get_latest_n(n)
    d.close()
    out = []
    for r in reversed(rows):
        out.append({"期号": r["issue"], "日期": r["date"],
                    "红球": r["reds"], "蓝球": r["blue"]})
    return json.dumps(out, ensure_ascii=False, indent=2)


def import_text(text):
    """粘贴导入开奖记录；返回导入条数。"""
    d = dbmod.DrawDB(_DB_PATH)
    n = d.import_text(text)
    d.close()
    return json.dumps({"导入条数": n}, ensure_ascii=False)


def import_csv(path):
    """从文件导入 CSV；返回导入条数。"""
    d = dbmod.DrawDB(_DB_PATH)
    n = d.import_csv(path)
    d.close()
    return json.dumps({"导入条数": n}, ensure_ascii=False)


def sync_draws(draws_json):
    """写入从福彩官网同步拉取的开奖记录（已存在期号覆盖更新）。
    返回：新增期数、官方最新期、本地最新期、断档状态。
    断档状态：0=衔接正常；-1=本地数据过旧（不在本次拉取范围内）。"""
    draws = json.loads(draws_json)
    d = dbmod.DrawDB(_DB_PATH)
    before = d.latest_issue()
    official_max = None
    added = 0
    for row in draws:
        issue = str(row.get("issue") or row.get("code") or "").strip()
        reds = row.get("reds") or []
        blue = int(row.get("blue") or 0)
        if not issue or len(reds) != 6 or not (1 <= blue <= 16):
            continue
        d.insert_draw(issue, str(row.get("date", "")), str(row.get("week", "")),
                      reds, blue, int(row.get("sales", 0)), int(row.get("pool", 0)),
                      replace=True)
        if official_max is None or issue > official_max:
            official_max = issue
        if before is None or issue > before:  # 期号为 7 位定长数字，字典序即数值序
            added += 1
    # 断档检测：跨年时相邻期号数值差可达数百上千，不能用差值估算期数缺口。
    # 改用"本地最新期是否在官方本次返回列表内"判断衔接：
    #   - 在列表内：衔接正常（本次能拉回的期都拉回来了）
    #   - 不在列表内且本地更旧：本地超过最近 N 期范围，缺口未知，提示手动导入
    missing = 0
    if before is not None:
        ids = sorted(int(r.get("issue") or r.get("code") or 0) for r in draws if r.get("issue") or r.get("code"))
        b = int(before)
        if ids and b < ids[0]:
            missing = -1
    last = d.latest_issue()
    total = len(d.get_all())
    d.close()
    return json.dumps({"写入条数": added, "官方最新期": official_max,
                       "同步前最新期": before, "最新期": last,
                       "总期数": total, "缺失期数": missing}, ensure_ascii=False)

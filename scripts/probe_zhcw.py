# -*- coding: utf-8 -*-
"""探测中彩网双色球历史开奖数据接口。"""
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"}


def get(url, referer="https://www.zhcw.com/"):
    h = dict(UA)
    h["Referer"] = referer
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "ignore")


candidates = [
    "https://kaijiang.zhcw.com/zhcw/inc/ssq/ssq_wqhg.jsp?num=50",
    "https://kaijiang.zhcw.com/pls/www/zhcw/ssq/kjgg_list.jsp?pageSize=50",
    "https://kaijiang.zhcw.com/ssq/kjgg/",
    "https://kaijiang.zhcw.com/ssq/kjgg_list.jsp",
]
for u in candidates:
    try:
        html = get(u)
        print(f"[OK] {u} len={len(html)}")
        print("  前300字:", html[:300].replace("\n", " "))
        print()
    except Exception as e:
        print(f"[ERR] {u}: {e}")

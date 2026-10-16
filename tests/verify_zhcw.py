# -*- coding: utf-8 -*-
"""验证中彩网分页解析：最后一页应为 2003 年数据。"""
import os, sys
sys.path.insert(0, r'E:\双色球智能选号\app')
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
      "Referer": "https://www.zhcw.com/"}

BASE = "https://kaijiang.zhcw.com/zhcw/inc/ssq/ssq_wqhg.jsp"


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")


def parse_page(html):
    """解析一页：返回 [(期号, 日期, 红球列表, 蓝球)]"""
    rows = re.findall(
        r"<td align=\"center\">(\d{4}-\d{2}-\d{2})</td>\s*"
        r"<td align=\"center\">(\d{7})</td>\s*"
        r"<td align=\"center\"[^>]*>(.*?)</td>",
        html, re.S)
    out = []
    for date, issue, cell in rows:
        reds = re.findall(r"class=\"rr\">(\d{2})</em>", cell)
        blues = re.findall(r"<em>(\d{2})</em>", cell)
        if len(reds) == 6 and blues:
            out.append((issue, date, [int(x) for x in reds], int(blues[0])))
    return out


for page in (1, 2, 175, 176):
    html = fetch(f"{BASE}?pageNum={page}")
    data = parse_page(html)
    if data:
        first, last = data[0], data[-1]
        print(f"pageNum={page}: {len(data)} 行, "
              f"{first[0]}({first[1]}) ~ {last[0]}({last[1]})")
        if page in (175, 176):
            print("  样例:", data[0])
    else:
        print(f"pageNum={page}: 解析失败 len={len(html)}")

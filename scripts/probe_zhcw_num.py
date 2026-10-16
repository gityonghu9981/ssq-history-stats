# -*- coding: utf-8 -*-
"""测试中彩网接口的参数能力。"""
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
      "Referer": "https://www.zhcw.com/"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")


def issues_range(html):
    iss = sorted(set(re.findall(r"(\d{7})", html)))
    return iss


for url in (
    "https://kaijiang.zhcw.com/zhcw/inc/ssq/ssq_wqhg.jsp?num=500",
    "https://kaijiang.zhcw.com/zhcw/inc/ssq/ssq_wqhg.jsp?num=2000",
    "https://kaijiang.zhcw.com/zhcw/inc/ssq/ssq_wqhg.jsp?num=4000",
):
    try:
        html = fetch(url)
        iss = issues_range(html)
        print(f"{url}\n  期数={len(iss)} 范围={iss[0] if iss else '-'} ~ {iss[-1] if iss else '-'}\n")
    except Exception as e:
        print(f"{url} ERR: {e}\n")

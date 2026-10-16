# -*- coding: utf-8 -*-
"""抓中彩网开奖频道首页找双色球历史数据入口。"""
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
      "Referer": "https://www.zhcw.com/"}

for url in ("https://kaijiang.zhcw.com/",
            "https://kaijiang.zhcw.com/ssq/"):
    try:
        req = urllib.request.Request(url, headers=UA)
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        links = re.findall(r'href=["\']([^"\']*ssq[^"\']*)["\']', html)
        print(f"[{url}] len={len(html)} ssq链接: {list(dict.fromkeys(links))[:20]}")
    except Exception as e:
        print(f"[{url}] ERR: {e}")

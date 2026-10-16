# -*- coding: utf-8 -*-
"""探测中彩网 list.html 分页模式。"""
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
      "Referer": "https://www.zhcw.com/"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")


html = fetch("http://kaijiang.zhcw.com/zhcw/html/ssq/list.html")
print("len:", len(html))
# 找分页链接
pages = re.findall(r'href=["\']([^"\']*list[^"\']*)["\']', html)
print("list链接:", list(dict.fromkeys(pages))[:20])
# 找页码
nums = re.findall(r"(\d+)\s*</a>", html)
print("页码提示:", nums[:20])
# 数据行样例
rows = re.findall(r"(\d{7})\s+([\d\s]{10,})\s+(\d{2})", html)
print("数据行数:", len(rows), "样例:", rows[:3])
# 是否有 js 分页函数
for fn in re.findall(r"""(?:onclick|href)=["']javascript:([^"']+)["']""", html)[:10]:
    print("JS:", fn)

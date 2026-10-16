# -*- coding: utf-8 -*-
"""分析中彩网 wqhg.jsp 页面数据加载机制。"""
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
      "Referer": "https://www.zhcw.com/"}
req = urllib.request.Request(
    "https://kaijiang.zhcw.com/zhcw/inc/ssq/ssq_wqhg.jsp?num=20", headers=UA)
html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")

# iframe / script src / 数据 url
for pat, label in [
    (r'<iframe[^>]*src=["\']([^"\']+)["\']', "iframe"),
    (r'<script[^>]*src=["\']([^"\']+)["\']', "script"),
    (r'(?:url|href|action)\s*[:=]\s*["\']([^"\']*ssq[^"\']*)["\']', "ssq-url"),
    (r'(?:url|href|action)\s*[:=]\s*["\']([^"\']*(?:jsp|do|json|xml)[^"\']*)["\']', "data-url"),
]:
    found = list(dict.fromkeys(re.findall(pat, html)))
    print(f"== {label}: {found[:15]}")
# 表单
for m in re.findall(r"<form[^>]*>", html)[:5]:
    print("FORM:", m)
print("总长:", len(html))

# -*- coding: utf-8 -*-
"""解析中彩网往期回顾页面结构。"""
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
      "Referer": "https://www.zhcw.com/"}
req = urllib.request.Request(
    "https://kaijiang.zhcw.com/zhcw/inc/ssq/ssq_wqhg.jsp?num=50", headers=UA)
html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")

# 找表格行：期号 + 日期 + 号码
issues = re.findall(r"(\d{7})", html)
dates = re.findall(r"(\d{4}-\d{2}-\d{2})", html)
reds = re.findall(r"(\d{2}\s+\d{2}\s+\d{2}\s+\d{2}\s+\d{2}\s+\d{2})", html)
print("期号数:", len(set(issues)), "日期数:", len(dates), "红球串数:", len(reds))
print("期号样例:", sorted(set(issues))[:10])
print("红球样例:", reds[:5])
# 检查分页/年份参数
for m in re.findall(r"(?:name|id)=[\"']?(\w+)", html)[:20]:
    print("字段:", m)
# 输出主体结构片段
body = re.sub(r"\s+", " ", html)
idx = body.find("期号")
print("…", body[idx:idx + 600] if idx >= 0 else body[:600])

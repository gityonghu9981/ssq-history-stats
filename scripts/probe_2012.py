# -*- coding: utf-8 -*-
"""确认福彩接口 2012 年边界 + 探测中彩网历史数据来源。"""
import json
import urllib.request
import urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
      "Referer": "https://www.cwl.gov.cn/"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def api(year, by_date=False):
    params = {"name": "ssq", "pageNo": 1, "pageSize": 500}
    if by_date:
        params["dayStart"] = f"{year}-01-01"
        params["dayEnd"] = f"{year}-12-31"
    else:
        params["issueStart"] = f"{year}001"
        params["issueEnd"] = f"{year}999"
    url = ("https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?"
           + urllib.parse.urlencode(params))
    try:
        obj = json.loads(get(url))
        return len(obj.get("result") or [])
    except Exception as e:
        return f"err:{e}"


print("福彩接口按期号:", {y: api(y) for y in (2014, 2013, 2012, 2011)})
print("福彩接口按日期:", {y: api(y, True) for y in (2012, 2011, 2003)})

# 中彩网历史页面
for u in ("https://www.zhcw.com/kjxx/ssq/",
          "https://www.zhcw.com/ssq/kjgg/"):
    try:
        html = get(u)
        print(f"\n[{u}] len={len(html)}")
        # 找期号样式的文本
        import re
        issues = re.findall(r"20\d{5}", html)[:10]
        print("期号样例:", issues)
    except Exception as e:
        print(f"[{u}] err: {e}")

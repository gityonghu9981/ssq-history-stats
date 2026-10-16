# -*- coding: utf-8 -*-
"""
双色球历史统计工具 —— 历史数据拉取
从中国福利彩票官网公开开奖数据接口拉取全部历史开奖记录。
接口：https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice
"""
import json
import time
import urllib.request
import urllib.parse

API = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
ZHCW_BASE = "https://kaijiang.zhcw.com/zhcw/inc/ssq/ssq_wqhg.jsp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def _request(params, timeout=20, retries=3):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    last_err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode("utf-8")
            obj = json.loads(data)
            if obj.get("state") == 0:
                return obj.get("result") or []
            raise RuntimeError("接口返回异常: " + obj.get("message", ""))
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (i + 1))
    raise last_err


def fetch_page(page_size=100, before_issue=None):
    """拉取 page_size 期（默认最新；before_issue 时拉取该期之前的）。
    返回 draw dict 列表（期号降序）。"""
    params = {"name": "ssq", "issueCount": page_size,
              "pageNo": 1, "pageSize": page_size}
    if before_issue:
        params["issueEnd"] = before_issue
    raw = _request(params)
    return [_normalize(r) for r in raw]


def fetch_all(stop_issue="2003001", page_size=500, progress_cb=None,
              already_issues=()):
    """按年份分块拉取全部历史开奖记录（2003 年至今）。
    already_issues: 本地已有期号集合，用于去重续拉。
    返回 draw dict 列表（期号升序，去重）。"""
    all_rows = {}
    has = set(already_issues)
    current_year = _current_year()
    for year in range(2003, current_year + 1):
        start = f"{year}001"
        end = f"{year}999"
        try:
            raw = _request({"name": "ssq", "issueStart": start,
                            "issueEnd": end, "pageNo": 1, "pageSize": page_size,
                            "issueCount": page_size})
        except Exception:
            continue  # 单年失败不阻塞整体，可在日志中体现
        batch = [_normalize(r) for r in raw if str(r.get("code", "")).startswith(str(year))]
        new_rows = []
        for d in batch:
            if d["issue"] in has or d["issue"] in all_rows:
                continue
            all_rows[d["issue"]] = d
            new_rows.append(d)
        if progress_cb and new_rows:
            progress_cb(len(all_rows), batch[-1]["issue"] if batch else f"{year}001")
        time.sleep(0.3)
    return sorted(all_rows.values(), key=lambda d: d["issue"])


def _current_year():
    import datetime
    return datetime.date.today().year


# ============================================================
# 中彩网（福彩官方直属网站）全量历史数据
# 覆盖 2003 年至今全部期数，按 pageNum 分页（每页 20 期）
# ============================================================

def _zhcw_request(url, retries=3):
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/120.0",
        "Referer": "https://www.zhcw.com/",
    }
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (i + 1))
    raise last_err


def _zhcw_parse_page(html):
    """解析中彩网一页，返回 [(issue, date, reds, blue)]。"""
    import re
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
            out.append((str(issue), date, [int(x) for x in reds], int(blues[0])))
    return out


def fetch_zhcw_all(max_pages=200, progress_cb=None, already_issues=()):
    """拉取中彩网全量历史（2003 年至今）。
    返回 draw dict 列表（期号升序，去重）。"""
    has = set(already_issues)
    all_rows = {}
    for page in range(1, max_pages + 1):
        url = f"{ZHCW_BASE}?pageNum={page}"
        try:
            html = _zhcw_request(url)
        except Exception:
            break  # 网络失败停止（数据已入库部分保留）
        rows = _zhcw_parse_page(html)
        if not rows:
            break
        for issue, date, reds, blue in rows:
            if issue in has or issue in all_rows:
                continue
            all_rows[issue] = {
                "issue": issue, "date": date, "week": "",
                "reds": reds, "blue": blue, "sales": 0, "pool": 0,
            }
        if progress_cb:
            progress_cb(len(all_rows), rows[0][0])
        time.sleep(0.25)
    return sorted(all_rows.values(), key=lambda d: d["issue"])


def _normalize(r):
    reds = [int(x) for x in str(r.get("red", "")).split(",") if x.strip()]
    return {
        "issue": str(r.get("code", "")).strip(),
        "date": str(r.get("date", "")).split("(")[0].strip(),
        "week": str(r.get("week", "")).strip(),
        "reds": sorted(reds),
        "blue": int(r.get("blue", 0)),
        "sales": _to_int(r.get("sales")),
        "pool": _to_int(r.get("poolmoney")),
    }


def _to_int(v):
    try:
        return int(float(str(v or 0)))
    except (ValueError, TypeError):
        return 0

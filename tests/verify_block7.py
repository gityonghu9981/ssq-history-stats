# -*- coding: utf-8 -*-
"""修复后全量回测回归：3410 期分块子进程，验证回测结论仍与随机基准相当。"""
import json
import os
import subprocess
import sys
import time

APP = r"E:\双色球智能选号\app"
DB = r"E:\双色球智能选号\dist\data\ssq.db"
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"
MAIN = os.path.join(APP, "main.py")

sys.path.insert(0, APP)
from db import DrawDB
from backtest import Backtest

n_total = DrawDB(DB).count()
WINDOW = 100
BLOCK = 100
begin = n_total - WINDOW  # 回测起点（全量：起点=窗口后）
# 全量：start=window 期之后全部（3410 期）
begin = WINDOW
rounds = n_total - WINDOW
t0 = time.time()
blocks_raw = []
idx = 0
t = begin
while t < n_total:
    t_end = min(t + BLOCK, n_total)
    out_json = os.path.join(os.environ["TEMP"], f"bt7_{idx}.json")
    if os.path.exists(out_json):
        os.remove(out_json)
    cmd = [PY, MAIN, "--bt-block",
           "--start", str(t), "--end", str(t_end),
           "--window", str(WINDOW), "--sample", "1500",
           "--db-path", DB, "--out-json", out_json]
    p = subprocess.run(cmd, capture_output=True, timeout=1800)
    tries = 0
    while (p.returncode != 0 or not os.path.exists(out_json)) and tries < 3:
        # 本机安全软件 hook 偶发致子进程崩溃（0xC0000005 概率性）：重试最多 3 次
        tries += 1
        if os.path.exists(out_json):
            os.remove(out_json)
        print(f"  块 {t}-{t_end} 第 {tries} 次失败 code={p.returncode}，重试…")
        p = subprocess.run(cmd, capture_output=True, timeout=1800)
    if p.returncode != 0 or not os.path.exists(out_json):
        print(f"✗ 块 {t}-{t_end} 重试 {tries} 次仍失败 code={p.returncode}")
        sys.exit(1)
    with open(out_json, encoding="utf-8") as f:
        blocks_raw.append(json.load(f))
    os.remove(out_json)
    idx += 1
    if idx % 5 == 0 or t_end >= n_total:
        print(f"  完成块 {idx}/{rounds // BLOCK + 1}（{t}-{t_end}），"
              f"已用 {time.time() - t0:.0f}s")
    t = t_end

res = Backtest.merge_blocks(blocks_raw, WINDOW)
print(f"\n回测 {res['回测期数']} 期（窗口 {WINDOW}）共 {idx} 块，"
      f"总耗时 {time.time() - t0:.0f}s")
print(f"大底18码平均命中: {res['大底平均命中']:.3f}（随机基准 {res['随机基准红球']}）")
for k in ("结果1", "结果2", "结果3", "结果4", "结果5", "结果6"):
    s = res[k]
    tag = "（集合10码）" if k in ("结果2", "结果4", "结果6") else ""
    print(f"  {k}{tag}: 红球平均 {s['平均红球命中']:.3f}, "
          f"蓝球命中率 {s['蓝球命中率']*100:.2f}%")
prize = res["结果1"]["奖级分布"]
print(f"结果1奖级分布: {dict(prize)}")

# 结论判定
dev = []
for v, b, name in ((res['大底平均命中'], 6*18/33.0, "大底"),
                   (res["结果1"]["平均红球命中"], 6*6/33.0, "结果1"),
                   (res["结果2"]["平均红球命中"], 6*10/33.0, "结果2"),
                   (res["结果1"]["蓝球命中率"]*100, 6.25, "蓝球")):
    if abs(v - b) >= (0.30 if name == "大底" else 0.10 if name == "结果1" else 0.15 if name == "结果2" else 1.5):
        dev.append(name)
if dev:
    print(f"偏离随机项: {dev}（需关注）")
else:
    print("结论：全部指标与随机基准相当——统计选号无预测能力 ✅")

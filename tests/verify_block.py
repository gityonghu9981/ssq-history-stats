# -*- coding: utf-8 -*-
"""分块回测端到端验证：模拟 UI 调度，子进程跑全部块并合并。"""
import os, sys
sys.path.insert(0, r'E:\双色球智能选号\app')
import json, os, subprocess, sys, tempfile, time

db_path = r"E:\双色球智能选号\dist\data\ssq.db"
exe = sys.executable
from db import DrawDB
db = DrawDB(db_path)
n = db.count()
db.close()

window = 100
begin = min(window, n)
rounds = n - begin
BLOCK = 100
main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
if getattr(sys, "frozen", False):
    base = [exe]
else:
    base = [exe, main_py]
t0 = time.time()
blocks = []
t = begin
idx = 0
while t < n:
    t_end = min(t + BLOCK, n)
    out_json = os.path.join(tempfile.gettempdir(), f"btv_{os.getpid()}_{idx}.json")
    cmd = base + ["--bt-block", "--start", str(t), "--end", str(t_end),
                  "--window", str(window), "--sample", "1500",
                  "--db-path", db_path, "--out-json", out_json]
    ok = False
    for _attempt in range(3):
        p = subprocess.run(cmd, capture_output=True)
        if p.returncode == 0 and os.path.exists(out_json):
            ok = True
            break
        if os.path.exists(out_json):
            os.remove(out_json)
    if not ok:
        print(f"✗ 块 {t}-{t_end} 3次尝试均失败 exit={p.returncode}")
        sys.exit(1)
    with open(out_json, encoding="utf-8") as f:
        blocks.append(json.load(f))
    os.remove(out_json)
    print(f"✓ 块 {t}-{t_end} OK", flush=True)
    t = t_end
    idx += 1

from backtest import Backtest
res = Backtest.merge_blocks(blocks, window)
dt = time.time() - t0
print(f"\n合并完成: {res['回测期数']} 期 耗时 {dt:.0f}s")
print(f"大底平均命中: {res['大底平均命中']:.3f} (随机 {res['随机基准红球']})")
print(f"结果1: 平均红球 {res['结果1']['平均红球命中']:.3f}, 蓝球 {res['结果1']['蓝球命中率']*100:.1f}%, 奖级 {res['结果1']['奖级分布']}")
print(f"结果2(集合): 平均红球 {res['结果2']['平均红球命中']:.3f}, 蓝球 {res['结果2']['蓝球命中率']*100:.1f}%")
print("分块全量回测验证通过 ✅")

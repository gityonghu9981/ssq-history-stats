# -*- coding: utf-8 -*-
"""EXE 冒烟：块子进程入口 + 数据目录 + 3块合并。"""
import json, os, subprocess, sys, tempfile

EXE = r"E:\双色球智能选号\dist\双色球智能选号\双色球智能选号.exe"
data_dir = r"E:\双色球智能选号\dist\双色球智能选号\data"
print("data 目录:", os.path.exists(data_dir))
for f in os.listdir(data_dir):
    print("  ", f, os.path.getsize(os.path.join(data_dir, f)))

db_path = os.path.join(data_dir, "ssq.db")
blocks = []
t = 100
idx = 0
while t < 400:
    t_end = t + 100
    out_json = os.path.join(tempfile.gettempdir(), f"smoke_{os.getpid()}_{idx}.json")
    cmd = [EXE, "--bt-block", "--start", str(t), "--end", str(t_end),
           "--window", "100", "--sample", "1500",
           "--db-path", db_path, "--out-json", out_json]
    ok = False
    for _attempt in range(2):
        p = subprocess.run(cmd, capture_output=True, timeout=300)
        if p.returncode == 0 and os.path.exists(out_json):
            ok = True
            break
        if os.path.exists(out_json):
            os.remove(out_json)
    if not ok:
        print(f"✗ 块 {t}-{t_end} 两次尝试均失败 exit={p.returncode}")
        print("stderr:", p.stderr.decode("utf-8", "replace")[:500])
        sys.exit(1)
    with open(out_json, encoding="utf-8") as f:
        blocks.append(json.load(f))
    os.remove(out_json)
    print(f"✓ EXE 块 {t}-{t_end} OK", flush=True)
    t = t_end
    idx += 1

sys.path.insert(0, r"E:\双色球智能选号\app")
from backtest import Backtest
res = Backtest.merge_blocks(blocks, 100)
print(f"\nEXE 冒烟通过: {res['回测期数']} 期, 大底平均命中 {res['大底平均命中']:.3f}")

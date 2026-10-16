# -*- coding: utf-8 -*-
"""等价性铁证（进程隔离版）：同一 200 期，单进程 vs 分块 2×100 子进程，结果逐项一致。
主进程只做调度与比对（轻量），各子进程独立运行 20-40 秒（安全区内）。"""
import json
import os
import subprocess
import sys
import tempfile

PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"
MAIN = r"E:\双色球智能选号\app\main.py"
DB = r"E:\双色球智能选号\dist\data\ssq.db"
BEGIN, N = 3310, 3510
W = 100

def run_block(start, end, tag):
    out = os.path.join(tempfile.gettempdir(), f"eq_{os.getpid()}_{tag}.json")
    p = subprocess.run([PY, MAIN, "--bt-block", "--start", str(start),
                        "--end", str(end), "--window", str(W), "--sample", "1500",
                        "--db-path", DB, "--out-json", out],
                       capture_output=True, timeout=300)
    assert p.returncode == 0 and os.path.exists(out), f"{tag} 失败 exit={p.returncode}"
    with open(out, encoding="utf-8") as f:
        data = json.load(f)
    os.remove(out)
    return data

sys.path.insert(0, r"E:\双色球智能选号\app")
from backtest import Backtest

# 单进程 200 期（一个独立进程，约 40 秒，安全区内）
single_raw = run_block(BEGIN, N, "single")

# 分块 2×100 期（两个独立进程，各约 20 秒）
raw1 = run_block(BEGIN, BEGIN + 100, "b1")
raw2 = run_block(BEGIN + 100, N, "b2")

# 转换视图并断言完全一致
single_view = Backtest.merge_blocks([single_raw], W)
blocked_view = Backtest.merge_blocks([raw1, raw2], W)

print("单进程视图: 期数=%d 大底平均=%.6f 大底分布=%s" % (
    single_view["回测期数"], single_view["大底平均命中"],
    single_view["大底命中分布"]))
print("分块合并视图: 期数=%d 大底平均=%.6f 大底分布=%s" % (
    blocked_view["回测期数"], blocked_view["大底平均命中"],
    blocked_view["大底命中分布"]))
print("结果1 单进程:", single_view["结果1"])
print("结果1 分块:  ", blocked_view["结果1"])
print("结果2 单进程:", single_view["结果2"])
print("结果2 分块:  ", blocked_view["结果2"])

assert single_view == blocked_view, "分块与单进程结果不一致！"
print("\n✅ 等价性成立：单进程与分块子进程的结果逐项完全一致，准确率零损失")

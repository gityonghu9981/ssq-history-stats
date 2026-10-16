# -*- coding: utf-8 -*-
"""V1.1.0 EXE 子进程回测通道验证：调 EXE --bt-block，检查输出文件。"""
import os
import subprocess
import sys
import time

EXE = r"E:\双色球智能选号\dist\双色球智能选号\双色球智能选号.exe"
DB = r"E:\双色球智能选号\dist\双色球智能选号\data\ssq.db"
LOG = os.path.join(os.environ["TEMP"], "bt_exe2_log.txt")

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

out = os.path.join(os.environ["TEMP"], "bt_exe2.json")
if os.path.exists(out):
    os.remove(out)
if os.path.exists(LOG):
    os.remove(LOG)

cmd = [EXE, "--bt-block",
       "--start", "3310", "--end", "3410",
       "--window", "100", "--sample", "1500",
       "--db-path", DB, "--out-json", out]
log("启动 EXE 子进程块: 3310-3410（窗口100）…")
p = subprocess.Popen(cmd)
t0 = time.time()
while time.time() - t0 < 120:
    if os.path.exists(out):
        break
    if p.poll() is not None and not os.path.exists(out):
        log(f"✗ 子进程提前退出 code={p.returncode}")
        sys.exit(1)
    time.sleep(2)
else:
    log("✗ 超时未生成输出文件")
    p.kill()
    sys.exit(1)

import json
with open(out, encoding="utf-8") as f:
    r = json.load(f)
log(f"✅ 子进程块完成: rounds={r['rounds']}, 大底命中sum={r['pool_sum']}, "
    f"结果1红球命中sum={r['结果1']['red_sum']}")
os.remove(out)
log("EXE 回测子进程通道正常")

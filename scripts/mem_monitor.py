# -*- coding: utf-8 -*-
"""全量回测内存监控：每 500 期打印进程内存。"""
import ctypes
from ctypes import wintypes
from db import DrawDB
from backtest import Backtest

class PMCounters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]

def rss_mb():
    c = PMCounters()
    c.cb = ctypes.sizeof(PMCounters)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 1048576

db = DrawDB()
red = db.red_sequences()
blue = db.blue_sequences()
print(f"开始: {len(red)} 期, 内存 {rss_mb():.0f} MB")

def cb(done, total):
    if done % 500 == 0 or done == total:
        print(f"  进度 {done}/{total}  内存 {rss_mb():.0f} MB", flush=True)

bt = Backtest(red, blue, window=100, max_rounds=None, block_sample=1500)
res = bt.run(progress_cb=cb)
print(f"完成: {res['回测期数']} 期, 内存 {rss_mb():.0f} MB, 大底命中 {res['大底平均命中']:.3f}")
db.close()

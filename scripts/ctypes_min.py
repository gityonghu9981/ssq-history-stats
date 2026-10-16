# -*- coding: utf-8 -*-
"""最小 ctypes 调用测试。"""
import ctypes
from ctypes import wintypes

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

print("开始最小ctypes测试")
h = ctypes.windll.kernel32.GetCurrentProcess()
print("GetCurrentProcess ok:", h)
c = PMCounters()
c.cb = ctypes.sizeof(PMCounters)
r = ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb)
print("GetProcessMemoryInfo ret:", r, "WorkingSet MB:", c.WorkingSetSize / 1048576)
print("最小ctypes测试通过")

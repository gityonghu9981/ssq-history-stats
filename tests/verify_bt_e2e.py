# -*- coding: utf-8 -*-
"""V1.1.0 预测率回测端到端验证：真实分块子进程调度 + 新对照表显示。
窗口100 / 回测200期（2块×100期子进程）。"""
import os
import sys
import shutil
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\双色球智能选号\app")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QEventLoop
from db import DrawDB
from ui_main import BacktestPage

SRC = r"E:\双色球智能选号\dist\data\ssq.db"
tmp = os.path.join(tempfile.gettempdir(), "ssq_e2e.db")
shutil.copy2(SRC, tmp)

db = DrawDB(tmp)
print(f"数据: {db.count()} 期")
app = QApplication([])
page = BacktestPage(db)

# 设置窗口100、回测200期（默认值），启动
page.spin_window.setValue(100)
page.spin_rounds.setValue(200)
page.run_backtest()
print("已启动回测（分块子进程调度）…")

loop = QEventLoop()
timer = QTimer()
timer.setSingleShot(True)
timer.timeout.connect(loop.quit)
page.worker.finished.connect(loop.quit)
timer.start(180000)  # 3 分钟上限
loop.exec()
timer.stop()

res = page._last_res if hasattr(page, "_last_res") else None
# 记录结果：包装 finished 拿 res
last = {}

def grab(r):
    last["res"] = r
page.worker.finished.connect(grab)
# 若回测已在上面 loop 结束前完成，重新触发一次回测
if "res" not in last:
    # 等信号再收一次
    loop2 = QEventLoop()
    page.worker.finished.connect(loop2.quit)
    page.worker.finished.connect(grab)
    timer2 = QTimer(); timer2.setSingleShot(True)
    timer2.timeout.connect(loop2.quit)
    timer2.start(180000)
    loop2.exec()
    timer2.stop()

r = last.get("res")
if r is None:
    print("✗ 未收到回测结果（可能超时或失败）")
    print(f"  按钮状态: enabled={page.btn_run.isEnabled()}")
    print(f"  状态文字: {page.lbl_result.text()[:120]}")
    sys.exit(1)

if "error" in r:
    print(f"✗ 回测报错: {r['error']}")
    sys.exit(1)

n = r["回测期数"]
print(f"✅ 回测完成: {n} 期（窗口 {r['窗口']}）")
print(f"   大底平均命中: {r['大底平均命中']:.3f}")
print("对照表:")
for i in range(1, 5):
    print("   ", " | ".join(page.cmp_table.item(i, c).text() for c in range(4)))
print(f"结论: {page.lbl_conclusion.text()[:80]}…")
assert n > 0, "回测期数为0"
assert page.lbl_conclusion.text().startswith("结论："), "结论缺失"

db.close()
os.remove(tmp)
print("\nV1.1.0 预测率回测端到端验证通过 ✅")
